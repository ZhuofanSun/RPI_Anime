from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
import http.client
import json
import os
import re
import shutil
import socket
from pathlib import Path
import sys
import threading
import time
from typing import Any
from urllib.parse import urlsplit

import requests
from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
TEMPLATE_DIR = APP_DIR / "templates"
REPO_ROOT = APP_DIR.parents[3]
POSTPROCESSOR_SRC = REPO_ROOT / "services" / "postprocessor" / "src"
if POSTPROCESSOR_SRC.exists() and str(POSTPROCESSOR_SRC) not in sys.path:
    sys.path.insert(0, str(POSTPROCESSOR_SRC))

from anime_ops_ui.copy import template_copy, text
from anime_ops_ui.i18n import resolve_locale
from anime_ops_ui.mobile.routes_auth import router as mobile_auth_router
from anime_ops_ui.mobile.routes_home import router as mobile_home_router
from anime_ops_ui.mobile.routes_items import router as mobile_items_router
from anime_ops_ui.mobile.routes_me import router as mobile_me_router
from anime_ops_ui.page_context import build_page_context
from anime_ops_ui.services.log_service import build_logs_payload as build_logs_payload_service
from anime_ops_ui.services.navigation_state_service import build_navigation_state as build_navigation_state_service
from anime_ops_ui.services.overview_service import build_overview_payload as build_overview_payload_service, build_service_summary
from anime_ops_ui.services.postprocessor_service import build_postprocessor_payload as build_postprocessor_payload_service
from anime_ops_ui.services.review_service import build_manual_review_item_payload as build_manual_review_item_payload_service, build_manual_review_payload as build_manual_review_payload_service
from anime_ops_ui.services.tailscale_service import build_tailscale_payload as build_tailscale_payload_service
from anime_postprocessor.models import ParsedMedia, UnparsedMedia
from anime_postprocessor.eventlog import append_event, clear_events, event_log_cap, event_log_path, read_events
from anime_postprocessor.parser import normalize_title, parse_media_file
from anime_postprocessor.publisher import build_target_path, publish_media
from anime_postprocessor.qb import QBClient
from anime_postprocessor.selector import score_candidate
from anime_postprocessor.watch import _build_groups, _should_process_group

MEDIA_EXTENSIONS = {".mkv", ".mp4", ".avi", ".m4v", ".ts"}
HISTORY_LOCK = threading.Lock()
HISTORY_SERIES = ("cpu_percent", "cpu_temp_c", "playback_tx_rate", "qb_active_downloads", "tailscale_online")
HISTORY_STATE: dict[str, Any] | None = None
TEMPLATES = Jinja2Templates(directory=str(TEMPLATE_DIR))
PAGE_TEMPLATES = {
    "/": ("dashboard.html", "dashboard", "Dashboard"),
    "/ops-review": ("ops_review.html", "ops-review", "Ops Review"),
    "/ops-review/item": ("ops_review_item.html", "ops-review", "Review Detail"),
    "/logs": ("logs.html", "logs", "Logs"),
    "/postprocessor": ("postprocessor.html", "postprocessor", "Postprocessor"),
    "/tailscale": ("tailscale.html", "tailscale", "Tailscale"),
}
OPS_UI_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}
SMALL_STORAGE_FALLBACK_THRESHOLD_BYTES = 100 * 1024 ** 3


def _ensure_canonical_main_module_alias(
    *,
    current_name: str | None = None,
    sys_modules: dict[str, Any] | None = None,
) -> None:
    name = current_name if current_name is not None else __name__
    if name != "__main__":
        return
    modules = sys_modules if sys_modules is not None else sys.modules
    dunder_main = modules.get("__main__")
    if dunder_main is None:
        return
    modules.setdefault("anime_ops_ui.main", dunder_main)


_ensure_canonical_main_module_alias()


class ManualPublishRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    season: int = Field(..., ge=1, le=99)
    episode: int = Field(..., ge=1, le=999)


class TailscaleActionRequest(BaseModel):
    action: str = Field(..., pattern="^(start|stop)$")


class ServiceRestartRequest(BaseModel):
    target: str = Field(..., min_length=1, max_length=64)


def render_page(request: Request, template_name: str, page_key: str, title: str):
    locale = resolve_locale(request)
    context = build_page_context(page_key, title, locale=locale)
    page_template_copy = template_copy(template_name.removesuffix(".html"), locale=locale)
    context["template_copy"] = page_template_copy
    context["page_title"] = page_template_copy.get("page_title", context["page_title"])
    return TEMPLATES.TemplateResponse(
        request,
        template_name,
        {"request": request, **context},
    )


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _service_link(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def _host_without_port(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    candidate = raw.split(",", 1)[0].strip()
    if not candidate:
        return None
    parsed = urlsplit(f"//{candidate}")
    return parsed.hostname or None


def _public_host(request: Request | None = None) -> str:
    fallback = _env("HOMEPAGE_BASE_HOST", socket.gethostname())
    if request is None:
        return fallback

    forwarded_host = _host_without_port(request.headers.get("x-forwarded-host"))
    if forwarded_host:
        return forwarded_host

    host_header = _host_without_port(request.headers.get("host"))
    if host_header:
        return host_header

    request_host = getattr(request.url, "hostname", None)
    if request_host:
        return request_host

    return fallback


def _safe_get_json(url: str, *, timeout: int = 5) -> tuple[dict[str, Any] | list[Any] | None, str | None]:
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json(), None
    except Exception as exc:  # pragma: no cover - defensive wrapper
        return None, str(exc)


def _count_media_files(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(1 for path in root.rglob("*") if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS)


def _count_series_dirs(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(1 for path in root.iterdir() if path.is_dir())


def _format_bytes(num_bytes: float | int | None) -> str:
    if num_bytes is None:
        return "-"
    value = float(num_bytes)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def _format_percent(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{float(value):.0f}%"


def _format_rate(num_bytes: float | int | None) -> str:
    if num_bytes is None:
        return "-"
    return f"{_format_bytes(num_bytes)}/s"


def _format_temperature(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{float(value):.1f}°C"


def _fan_state_file() -> Path:
    return Path(_env("FAN_CONTROL_STATE_FILE", "/host-fan/state.json"))


def _fan_state_snapshot() -> tuple[dict[str, Any] | None, str | None]:
    path = _fan_state_file()
    if not path.exists():
        return None, "fan state file not found"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, str(exc)
    if not isinstance(payload, dict):
        return None, "fan state payload was not valid JSON"
    return payload, None


def _format_uptime(value: str | None) -> str:
    if not value:
        return "-"
    parts = value.split(":")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        hours, minutes, _seconds = [int(part) for part in parts]
        return f"{hours}h {minutes}m"
    return value


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _extract_temperature(sensors: Any) -> float | None:
    if not isinstance(sensors, list):
        return None
    numeric_values = [float(item.get("value")) for item in sensors if isinstance(item, dict) and item.get("value") is not None]
    if not numeric_values:
        return None
    return sum(numeric_values) / len(numeric_values)


def _tailscale_ip_pair(value: Any) -> tuple[str, str]:
    if not isinstance(value, list) or not value:
        return "-", "-"
    ipv4 = str(value[0]) if value[0] else "-"
    ipv6 = str(value[1]) if len(value) > 1 and value[1] else "-"
    return ipv4, ipv6


def _glances_base_url() -> str:
    return _env("GLANCES_API_URL", "http://glances:61208/api/4").rstrip("/")


def _refresh_interval_seconds() -> int:
    return max(4, _env_int("OPS_UI_REFRESH_INTERVAL_SECONDS", 8))


def _sample_interval_seconds() -> int:
    return max(30, _env_int("OPS_UI_SAMPLE_INTERVAL_SECONDS", 60))


def _sampled_metric_freshness_seconds() -> int:
    return max(_sample_interval_seconds() * 5, 300)


def _series_window_hours() -> int:
    return max(6, _env_int("OPS_UI_SERIES_WINDOW_HOURS", 24))


def _upload_window_days() -> int:
    return max(3, _env_int("OPS_UI_UPLOAD_WINDOW_DAYS", 7))


def _history_root() -> Path:
    return Path(_env("OPS_UI_STATE_ROOT", "/tmp/ops-ui"))


def _history_file() -> Path:
    return _history_root() / "history.json"


def _default_history_state() -> dict[str, Any]:
    return {
        "samples": {name: [] for name in HISTORY_SERIES},
        "download_daily": {},
        "upload_daily": {},
        "last_download_total": None,
        "last_upload_total": None,
        "last_sample_ts": 0.0,
    }


def _ensure_history_root() -> None:
    _history_root().mkdir(parents=True, exist_ok=True)


def _load_history_state() -> dict[str, Any]:
    _ensure_history_root()
    path = _history_file()
    if not path.exists():
        return _default_history_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _default_history_state()

    state = _default_history_state()
    if isinstance(data, dict):
        samples = data.get("samples")
        if isinstance(samples, dict):
            for name in HISTORY_SERIES:
                raw_series = samples.get(name)
                if isinstance(raw_series, list):
                    state["samples"][name] = [
                        {
                            "ts": float(item.get("ts", 0)),
                            "value": float(item.get("value", 0)),
                        }
                        for item in raw_series
                        if isinstance(item, dict) and item.get("ts") is not None and item.get("value") is not None
                    ]

        upload_daily = data.get("upload_daily")
        if isinstance(upload_daily, dict):
            state["upload_daily"] = {
                str(day): float(value)
                for day, value in upload_daily.items()
                if value is not None
            }

        download_daily = data.get("download_daily")
        if isinstance(download_daily, dict):
            state["download_daily"] = {
                str(day): float(value)
                for day, value in download_daily.items()
                if value is not None
            }

        if data.get("last_download_total") is not None:
            state["last_download_total"] = float(data["last_download_total"])

        if data.get("last_upload_total") is not None:
            state["last_upload_total"] = float(data["last_upload_total"])
        if data.get("last_sample_ts") is not None:
            state["last_sample_ts"] = float(data["last_sample_ts"])
    return state


def _save_history_state(state: dict[str, Any]) -> None:
    _ensure_history_root()
    _history_file().write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def _prune_history_state(state: dict[str, Any], now_ts: float) -> None:
    keep_hours = max(_series_window_hours(), 24) + 24
    series_cutoff = now_ts - keep_hours * 3600
    samples = state.setdefault("samples", {})
    for name in HISTORY_SERIES:
        raw_series = samples.get(name, [])
        if not isinstance(raw_series, list):
            samples[name] = []
            continue
        samples[name] = [
            item
            for item in raw_series
            if isinstance(item, dict) and float(item.get("ts", 0)) >= series_cutoff
        ]

    oldest_day = (datetime.now().date() - timedelta(days=max(_upload_window_days(), 7) + 7)).isoformat()
    for daily_key in ("upload_daily", "download_daily"):
        daily = state.setdefault(daily_key, {})
        state[daily_key] = {
            str(day): float(value)
            for day, value in daily.items()
            if str(day) >= oldest_day
        }


def _record_daily_total(
    state: dict[str, Any],
    *,
    sample_ts: float,
    total: float | int | None,
    last_total_key: str,
    daily_key: str,
) -> None:
    if total is None:
        return
    total_value = float(total)
    previous_total = state.get(last_total_key)
    state[last_total_key] = total_value
    if previous_total is None:
        return
    delta = total_value - float(previous_total)
    if delta <= 0:
        return
    day_key = datetime.fromtimestamp(sample_ts).date().isoformat()
    daily = state.setdefault(daily_key, {})
    daily[day_key] = float(daily.get(day_key, 0.0)) + delta


def _downsample(values: list[float], *, max_points: int = 180) -> list[float]:
    if len(values) <= max_points:
        return values
    if max_points <= 1:
        return [values[-1]]
    step = (len(values) - 1) / (max_points - 1)
    return [values[round(index * step)] for index in range(max_points)]


def _series_values(name: str, *, window_hours: int, max_points: int = 180) -> tuple[list[float], list[float]]:
    cutoff = time.time() - window_hours * 3600
    with HISTORY_LOCK:
        global HISTORY_STATE
        if HISTORY_STATE is None:
            HISTORY_STATE = _load_history_state()
        raw_series = HISTORY_STATE.get("samples", {}).get(name, [])
        values = [
            float(item.get("value", 0))
            for item in raw_series
            if isinstance(item, dict) and float(item.get("ts", 0)) >= cutoff
        ]
    return values, _downsample(values, max_points=max_points)


def _latest_sampled_metric(name: str) -> float | None:
    cutoff_ts = time.time() - _sampled_metric_freshness_seconds()
    with HISTORY_LOCK:
        global HISTORY_STATE
        if HISTORY_STATE is None:
            HISTORY_STATE = _load_history_state()
        raw_series = HISTORY_STATE.get("samples", {}).get(name, [])
        if not isinstance(raw_series, list):
            return None
        for item in reversed(raw_series):
            if not isinstance(item, dict):
                continue
            sample_ts = item.get("ts")
            if sample_ts is None or float(sample_ts) < cutoff_ts:
                continue
            if item.get("value") is not None:
                return float(item.get("value"))
    return None


def _daily_volume_bars(*, days: int, daily_key: str) -> tuple[list[dict[str, Any]], list[float]]:
    today = datetime.now().date()
    with HISTORY_LOCK:
        global HISTORY_STATE
        if HISTORY_STATE is None:
            HISTORY_STATE = _load_history_state()
        daily_totals = HISTORY_STATE.get(daily_key, {})

    bars: list[dict[str, Any]] = []
    values: list[float] = []
    start = today - timedelta(days=days - 1)
    for offset in range(days):
        day = start + timedelta(days=offset)
        value = float(daily_totals.get(day.isoformat(), 0.0))
        bars.append(
            {
                "label": day.strftime("%m-%d"),
                "value": value,
                "value_label": _format_bytes(value),
            }
        )
        values.append(value)
    return bars, values


def _collect_history_metrics() -> dict[str, float | None]:
    quicklook, _ = _safe_get_json(f"{_glances_base_url()}/quicklook")
    sensors, _ = _safe_get_json(f"{_glances_base_url()}/sensors")
    containers_raw, _ = _safe_get_json(f"{_glances_base_url()}/containers")
    qb, _ = _qb_snapshot()
    tailscale_socket = _env("TAILSCALE_SOCKET", "/var/run/tailscale/tailscaled.sock")
    tailscale, _ = _tailscale_status(tailscale_socket)
    containers_list = containers_raw if isinstance(containers_raw, list) else []
    containers = {
        item.get("name", ""): item
        for item in containers_list
        if isinstance(item, dict)
    }
    jellyfin = containers.get("jellyfin", {})
    jellyfin_network = jellyfin.get("network", {}) if isinstance(jellyfin, dict) else {}
    tailscale_self = ((tailscale or {}).get("Self") or {}) if isinstance(tailscale, dict) else {}
    tailscale_online = bool(
        isinstance(tailscale, dict)
        and tailscale.get("BackendState") == "Running"
        and tailscale_self.get("Online")
    )
    return {
        "cpu_percent": (quicklook or {}).get("cpu") if isinstance(quicklook, dict) else None,
        "cpu_temp_c": _extract_temperature(sensors),
        "playback_tx_rate": float(jellyfin.get("network_tx") or jellyfin_network.get("tx") or 0.0),
        "qb_active_downloads": float((qb or {}).get("active_downloads", 0)) if qb else None,
        "tailscale_online": float(1.0 if tailscale_online else 0.0) if isinstance(tailscale, dict) else None,
        "uploaded_total": float((qb or {}).get("uploaded_total", 0)) if qb else None,
        "downloaded_total": float((qb or {}).get("downloaded_total", 0)) if qb else None,
    }


def _sample_history_once(*, force: bool = False) -> None:
    now_ts = time.time()
    with HISTORY_LOCK:
        global HISTORY_STATE
        if HISTORY_STATE is None:
            HISTORY_STATE = _load_history_state()
        last_sample_ts = float(HISTORY_STATE.get("last_sample_ts") or 0.0)
    if not force and now_ts - last_sample_ts < _sample_interval_seconds() * 0.95:
        return

    metrics = _collect_history_metrics()
    with HISTORY_LOCK:
        if HISTORY_STATE is None:
            HISTORY_STATE = _load_history_state()
        _prune_history_state(HISTORY_STATE, now_ts)
        samples = HISTORY_STATE.setdefault("samples", {})
        for name in HISTORY_SERIES:
            value = metrics.get(name)
            if value is None:
                continue
            samples.setdefault(name, []).append({"ts": now_ts, "value": float(value)})
        _record_daily_total(
            HISTORY_STATE,
            sample_ts=now_ts,
            total=metrics.get("uploaded_total"),
            last_total_key="last_upload_total",
            daily_key="upload_daily",
        )
        _record_daily_total(
            HISTORY_STATE,
            sample_ts=now_ts,
            total=metrics.get("downloaded_total"),
            last_total_key="last_download_total",
            daily_key="download_daily",
        )
        HISTORY_STATE["last_sample_ts"] = now_ts
        _save_history_state(HISTORY_STATE)


async def _history_sampler_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(_sample_history_once)
        except Exception:
            pass
        await asyncio.sleep(_sample_interval_seconds())


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, unix_socket_path: str, timeout: int, host: str = "local-unix-socket") -> None:
        super().__init__(host, timeout=timeout)
        self.unix_socket_path = unix_socket_path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.unix_socket_path)


def _unix_socket_request(
    socket_path: str,
    *,
    host: str,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    timeout: int = 5,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    try:
        connection = UnixHTTPConnection(socket_path, timeout=timeout, host=host)
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        request_headers = {"Host": host}
        if headers:
            request_headers.update(headers)
        if payload is not None:
            request_headers["Content-Type"] = "application/json"
            request_headers["Content-Length"] = str(len(payload))
        connection.request(method, path, body=payload, headers=request_headers)
        response = connection.getresponse()
        body = response.read()
        connection.close()
        text = body.decode("utf-8", "replace")
        data: dict[str, Any] | list[Any] | None = None
        if text:
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = None
        return {
            "status": response.status,
            "reason": response.reason,
            "text": text,
            "json": data,
        }
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc


def _tailscale_localapi_request(
    socket_path: str,
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    timeout: int = 5,
) -> dict[str, Any]:
    return _unix_socket_request(
        socket_path,
        host="local-tailscaled.sock",
        method=method,
        path=path,
        body=body,
        timeout=timeout,
        headers={"Sec-Tailscale": "localapi"},
    )


def _tailscale_status(socket_path: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = _tailscale_localapi_request(socket_path, "GET", "/localapi/v0/status", timeout=5)
        if response["status"] != 200:
            raise RuntimeError(f"{response['status']} {response['reason']}")
        data = response.get("json")
        if not isinstance(data, dict):
            raise RuntimeError("status payload was not valid JSON")
        return data, None
    except Exception as exc:  # pragma: no cover - defensive wrapper
        return None, str(exc)


def _tailscale_prefs(socket_path: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = _tailscale_localapi_request(socket_path, "GET", "/localapi/v0/prefs", timeout=5)
        if response["status"] != 200:
            raise RuntimeError(f"{response['status']} {response['reason']}")
        data = response.get("json")
        if not isinstance(data, dict):
            raise RuntimeError("prefs payload was not valid JSON")
        return data, None
    except Exception as exc:
        return None, str(exc)


def _tailscale_patch_prefs(socket_path: str, masked_prefs: dict[str, Any]) -> dict[str, Any]:
    response = _tailscale_localapi_request(socket_path, "PATCH", "/localapi/v0/prefs", body=masked_prefs, timeout=5)
    if int(response.get("status", 500)) >= 400:
        message = _tailscale_localapi_error_message(response)
        raise RuntimeError(message)
    data = response.get("json")
    if not isinstance(data, dict):
        raise RuntimeError("tailscale prefs patch did not return JSON")
    return data


def _docker_socket_path() -> str:
    return _env("DOCKER_SOCKET", "/var/run/docker.sock")


def _docker_api_version() -> str:
    return _env("DOCKER_API_VERSION", "v1.43").lstrip("/")


def _docker_api_request(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    timeout: int = 10,
) -> dict[str, Any]:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return _unix_socket_request(
        _docker_socket_path(),
        host="docker.sock",
        method=method,
        path=f"/{_docker_api_version()}{normalized_path}",
        body=body,
        timeout=timeout,
    )


def _docker_restart_container(container_name: str, *, timeout_seconds: int = 10) -> None:
    response = _docker_api_request(
        "POST",
        f"/containers/{container_name}/restart?t={timeout_seconds}",
        timeout=timeout_seconds + 5,
    )
    if int(response.get("status", 500)) not in {204}:
        raise RuntimeError(
            response.get("text") or f"docker restart failed for {container_name}: {response.get('status')} {response.get('reason')}"
        )


def _service_restart_specs() -> dict[str, dict[str, Any]]:
    return {
        "jellyfin": {"kind": "container", "container_name": "jellyfin", "label": "Jellyfin"},
        "qbittorrent": {"kind": "container", "container_name": "qbittorrent", "label": "qBittorrent"},
        "autobangumi": {"kind": "container", "container_name": "autobangumi", "label": "AutoBangumi"},
        "glances": {"kind": "container", "container_name": "glances", "label": "Glances"},
        "postprocessor": {"kind": "container", "container_name": "anime-postprocessor", "label": "Postprocessor"},
        "homepage": {"kind": "container", "container_name": "homepage", "label": "Ops UI"},
        "tailscale": {"kind": "tailscale", "label": "Tailscale"},
    }


def _stack_restart_targets() -> list[str]:
    return ["jellyfin", "qbittorrent", "autobangumi", "glances", "postprocessor", "homepage"]


def _append_service_control_event(
    *,
    level: str,
    action: str,
    message: str,
    target: str,
    details: dict[str, Any] | None = None,
) -> None:
    payload = {"target": target}
    if details:
        payload.update(details)
    append_event(
        source="service-control",
        level=level,
        action=action,
        message=message,
        details=payload,
    )


def _run_background(name: str, callback: Any) -> None:
    thread = threading.Thread(target=callback, name=name, daemon=True)
    thread.start()


def _qb_snapshot() -> tuple[dict[str, Any] | None, str | None]:
    base_url = _env("QBITTORRENT_API_URL", "http://qbittorrent:8080").rstrip("/")
    username = _env("QBITTORRENT_USERNAME", "")
    password = _env("QBITTORRENT_PASSWORD", "")
    category = _env("POSTPROCESSOR_CATEGORY", "Bangumi")

    session = requests.Session()
    try:
        auth = session.post(
            f"{base_url}/api/v2/auth/login",
            data={"username": username, "password": password},
            timeout=5,
        )
        auth.raise_for_status()
        if auth.text.strip() != "Ok.":
            raise RuntimeError(f"qB auth failed: {auth.text.strip()}")

        transfer = session.get(f"{base_url}/api/v2/transfer/info", timeout=5)
        transfer.raise_for_status()
        transfer_data = transfer.json()

        torrents = session.get(
            f"{base_url}/api/v2/torrents/info",
            params={"category": category},
            timeout=5,
        )
        torrents.raise_for_status()
        torrent_list = torrents.json()

        downloading_states = {
            "downloading",
            "metaDL",
            "forcedDL",
            "stalledDL",
            "queuedDL",
            "checkingDL",
        }
        seeding_states = {
            "uploading",
            "forcedUP",
            "stalledUP",
            "queuedUP",
            "pausedUP",
        }

        active_downloads = sum(1 for item in torrent_list if item.get("state") in downloading_states)
        active_seeds = sum(1 for item in torrent_list if item.get("state") in seeding_states)

        return {
            "category": category,
            "task_count": len(torrent_list),
            "active_downloads": active_downloads,
            "active_seeds": active_seeds,
            "download_speed": transfer_data.get("dl_info_speed", 0),
            "upload_speed": transfer_data.get("up_info_speed", 0),
            "downloaded_total": transfer_data.get("dl_info_data", 0),
            "uploaded_total": transfer_data.get("up_info_data", 0),
        }, None
    except Exception as exc:  # pragma: no cover - defensive wrapper
        return None, str(exc)


def _build_services(
    base_host: str,
    containers: dict[str, dict[str, Any]],
    tailscale: dict[str, Any] | None,
    *,
    manual_review_count: int | None,
    log_count: int,
) -> list[dict[str, Any]]:
    tailscale_self = ((tailscale or {}).get("Self") or {}) if isinstance(tailscale, dict) else {}
    tailscale_backend_running = (tailscale or {}).get("BackendState") == "Running"
    tailscale_state = "online" if tailscale_backend_running and tailscale_self.get("Online") else "offline"
    ops_ui_base = _service_link(base_host, int(_env("HOMEPAGE_PORT", "3000")))

    def container_uptime(name: str) -> str | None:
        container = containers.get(name, {})
        return container.get("uptime") if isinstance(container, dict) else None

    return [
        {
            "id": "jellyfin",
            "name": "Jellyfin",
            "href": _service_link(base_host, int(_env("JELLYFIN_PORT", "8096"))),
            "description": "私人影音库与播放入口",
            "status": containers.get("jellyfin", {}).get("status", "unknown"),
            "meta": "Media server",
            "uptime": container_uptime("jellyfin"),
            "restart_target": "jellyfin",
            "restart_label": "Restart",
        },
        {
            "id": "qbittorrent",
            "name": "qBittorrent",
            "href": _service_link(base_host, int(_env("QBITTORRENT_WEBUI_PORT", "8080"))),
            "description": "下载、任务队列和分类",
            "status": containers.get("qbittorrent", {}).get("status", "unknown"),
            "meta": "Download client",
            "uptime": container_uptime("qbittorrent"),
            "restart_target": "qbittorrent",
            "restart_label": "Restart",
        },
        {
            "id": "autobangumi",
            "name": "AutoBangumi",
            "href": _service_link(base_host, int(_env("AUTOBANGUMI_PORT", "7892"))),
            "description": "RSS 订阅与自动下载规则",
            "status": containers.get("autobangumi", {}).get("status", "unknown"),
            "meta": "Subscription",
            "uptime": container_uptime("autobangumi"),
            "restart_target": "autobangumi",
            "restart_label": "Restart",
        },
        {
            "id": "glances",
            "name": "Glances",
            "href": _service_link(base_host, int(_env("GLANCES_PORT", "61208"))),
            "description": "系统、容器和进程监控",
            "status": containers.get("glances", {}).get("status", "unknown"),
            "meta": "System monitor",
            "uptime": container_uptime("glances"),
            "restart_target": "glances",
            "restart_label": "Restart",
        },
        {
            "id": "postprocessor",
            "name": "Postprocessor",
            "href": f"{ops_ui_base}/postprocessor",
            "description": "下载完成后的选优、发布和 NFO 生成",
            "status": containers.get("anime-postprocessor", {}).get("status", "unknown"),
            "meta": "Background worker",
            "uptime": container_uptime("anime-postprocessor"),
            "internal": True,
            "restart_target": "postprocessor",
            "restart_label": "Restart",
        },
        {
            "id": "ops-review",
            "name": "Ops Review",
            "href": f"{ops_ui_base}/ops-review",
            "description": "人工审核队列与文件处理",
            "status": "online",
            "meta": f"{manual_review_count} files" if manual_review_count is not None else "数据盘未挂载",
            "uptime": "审核工作台",
            "internal": True,
            "restart_target": "homepage",
            "restart_label": "Restart UI",
            "restart_requires_reload": True,
            "restart_name": "Ops UI",
        },
        {
            "id": "logs",
            "name": "Logs",
            "href": f"{ops_ui_base}/logs",
            "description": "结构化日志、来源筛选和清理",
            "status": "online",
            "meta": f"{log_count} events",
            "uptime": f"上限 {event_log_cap()} 条",
            "internal": True,
            "restart_target": "homepage",
            "restart_label": "Restart UI",
            "restart_requires_reload": True,
            "restart_name": "Ops UI",
        },
        {
            "id": "tailscale",
            "name": "Tailscale",
            "href": f"{ops_ui_base}/tailscale",
            "description": "本地 tailnet 状态与远程访问链路",
            "status": tailscale_state,
            "meta": _tailscale_ip_pair(tailscale_self.get("TailscaleIPs") if tailscale_self else None)[0],
            "uptime": _strip_trailing_dot(tailscale_self.get("DNSName")) if tailscale_self else None,
            "internal": True,
            "restart_target": "tailscale",
            "restart_label": "Restart",
        },
    ]


def _disk_snapshot(anime_data_root: Path) -> dict[str, Any]:
    usage = shutil.disk_usage(anime_data_root)
    used = usage.total - usage.free
    percent = (used / usage.total * 100) if usage.total else 0.0
    return {
        "path": str(anime_data_root),
        "used_bytes": used,
        "free_bytes": usage.free,
        "total_bytes": usage.total,
        "percent": percent,
    }


def _is_mounted_path(path: Path) -> bool:
    target = str(path)
    try:
        with open("/proc/self/mountinfo", "r", encoding="utf-8") as handle:
            for line in handle:
                parts = line.split()
                if len(parts) > 4 and parts[4] == target:
                    return True
    except OSError:
        pass
    return path.is_mount()


def _mount_health(path: Path) -> dict[str, Any]:
    mounted = _is_mounted_path(path)
    exists = path.exists()
    readable = False
    probe_error: str | None = None

    try:
        if not exists:
            raise FileNotFoundError(str(path))
        with os.scandir(path) as iterator:
            next(iterator, None)
        readable = True
    except Exception as exc:
        probe_error = str(exc)

    return {
        "path": str(path),
        "mounted": mounted,
        "exists": exists,
        "readable": readable,
        "probe_error": probe_error,
    }


def _storage_roots_share_small_system_disk(primary: Path, secondary: Path) -> bool:
    if not (str(primary).startswith("/srv/") and str(secondary).startswith("/srv/")):
        return False
    try:
        primary_device = primary.stat().st_dev
        secondary_device = secondary.stat().st_dev
        if primary_device != secondary_device:
            return False
        primary_total = shutil.disk_usage(primary).total
        secondary_total = shutil.disk_usage(secondary).total
    except OSError:
        return False
    return (
        abs(primary_total - secondary_total) <= 1024 * 1024
        and primary_total < SMALL_STORAGE_FALLBACK_THRESHOLD_BYTES
    )


def _manual_review_root() -> Path:
    anime_data_root = Path(_env("ANIME_DATA_ROOT", "/srv/anime-data"))
    return anime_data_root / "processing" / "manual_review"


def _library_root() -> Path:
    anime_data_root = Path(_env("ANIME_DATA_ROOT", "/srv/anime-data"))
    return anime_data_root / "library" / "seasonal"


def _format_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def _strip_trailing_dot(value: str | None) -> str:
    if not value:
        return "-"
    return value.rstrip(".")


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value or value.startswith("0001-01-01"):
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _format_iso_datetime(value: str | None) -> str:
    parsed = _parse_iso_datetime(value)
    if not parsed:
        return "-"
    return parsed.strftime("%Y-%m-%d %H:%M")


def _review_bucket_reason(bucket: str) -> str:
    reason_map = {
        "unparsed": "无法稳定解析标题或季集信息",
        "duplicates": "重复版本等待人工处理",
        "failed": "自动处理过程中出现异常",
    }
    return reason_map.get(bucket, "等待人工审核")


def _cleanup_empty_dirs(path: Path, stop_at: Path) -> None:
    current = path
    while current != stop_at and current.is_dir():
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def _season_number_from_label(season_label: str | None) -> int:
    if not season_label:
        return 1
    digits = "".join(ch for ch in season_label if ch.isdigit())
    if not digits:
        return 1
    try:
        return max(1, int(digits))
    except ValueError:
        return 1


def _guess_episode_number(name: str) -> int | None:
    patterns = (
        r"\bS\d{1,2}E(?P<episode>\d{1,3})\b",
        r"第(?P<episode>\d{1,3})[话話集]",
        r"\[(?P<episode>\d{1,3})(?:v\d+)?\]",
        r"(?:^|[\s._-])(?P<episode>\d{1,3})(?:v\d+)?(?=[\s._-]|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, name, re.IGNORECASE)
        if not match:
            continue
        try:
            return int(match.group("episode"))
        except (ValueError, IndexError):
            continue
    return None


def _manual_review_item_or_404(item_id: str) -> tuple[dict[str, Any], Path, Path]:
    review_root = _manual_review_root()
    try:
        payload = build_manual_review_item_payload_service(item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="manual review file not found") from exc
    item = payload["item"]
    item_path = review_root / item["relative_path"]
    if not item_path.exists() or not item_path.is_file():
        raise HTTPException(status_code=404, detail="manual review file not found")
    return item, item_path, review_root


def _build_auto_parse_payload(item_path: Path, review_root: Path) -> dict[str, Any]:
    parsed = parse_media_file(review_root, item_path)
    if isinstance(parsed, UnparsedMedia):
        return {
            "status": "unparsed",
            "reason": parsed.reason,
            "target_path": None,
            "target_exists": False,
            "score_summary": None,
            "parsed": None,
        }

    target = build_target_path(_library_root(), parsed)
    return {
        "status": "parsed",
        "reason": None,
        "target_path": str(target),
        "target_exists": target.exists(),
        "score_summary": score_candidate(parsed).summary,
        "parsed": {
            "title": parsed.title,
            "season": parsed.season,
            "episode": parsed.episode,
            "extension": parsed.extension,
        },
    }


def _manual_publish_defaults(item: dict[str, Any], auto_parse: dict[str, Any]) -> dict[str, Any]:
    parsed = auto_parse.get("parsed") if isinstance(auto_parse, dict) else None
    default_title = (
        parsed.get("title")
        if isinstance(parsed, dict) and parsed.get("title")
        else item.get("series_name")
        or item.get("stem")
        or item.get("filename")
    )
    season = (
        parsed.get("season")
        if isinstance(parsed, dict) and parsed.get("season") is not None
        else _season_number_from_label(item.get("season_label"))
    )
    episode = (
        parsed.get("episode")
        if isinstance(parsed, dict) and parsed.get("episode") is not None
        else _guess_episode_number(item.get("filename", "")) or 1
    )
    return {
        "title": default_title,
        "season": season,
        "episode": episode,
    }


def _review_item_from_path(path: Path, review_root: Path) -> dict[str, Any]:
    relative = path.relative_to(review_root)
    parts = list(relative.parts)
    bucket = parts[0] if parts else "root"
    logical_parts = parts[1:] if len(parts) > 1 else []
    series_name = logical_parts[0] if logical_parts else path.stem
    season_label = None
    nested_parts = logical_parts[1:-1] if len(logical_parts) > 2 else []
    if len(logical_parts) >= 2 and logical_parts[1].lower().startswith("season"):
        season_label = logical_parts[1]
    folder_hint = " / ".join(nested_parts) if nested_parts else "-"
    stat = path.stat()
    return {
        "id": str(relative).replace("/", "__"),
        "bucket": bucket,
        "reason": _review_bucket_reason(bucket),
        "relative_path": str(relative),
        "filename": path.name,
        "stem": path.stem,
        "extension": path.suffix.lower() or "-",
        "series_name": series_name,
        "season_label": season_label or "-",
        "folder_hint": folder_hint,
        "size_bytes": stat.st_size,
        "size_label": _format_bytes(stat.st_size),
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "modified_label": _format_timestamp(stat.st_mtime),
    }


def _manual_review_items(review_root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not review_root.exists():
        return items
    for path in sorted(review_root.rglob("*")):
        if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS:
            items.append(_review_item_from_path(path, review_root))
    items.sort(key=lambda item: item["modified_at"], reverse=True)
    return items


def _postprocessor_paths() -> dict[str, Path]:
    anime_data_root = Path(_env("ANIME_DATA_ROOT", "/srv/anime-data"))
    return {
        "anime_data_root": anime_data_root,
        "source_root": anime_data_root / "downloads" / "Bangumi",
        "target_root": anime_data_root / "library" / "seasonal",
        "review_root": anime_data_root / "processing" / "manual_review",
        "title_map": Path(_env("POSTPROCESSOR_TITLE_MAP", str(anime_data_root / "appdata" / "rpi-anime" / "deploy" / "title_mappings.toml"))),
    }


def _glances_containers_snapshot() -> tuple[dict[str, dict[str, Any]], str | None]:
    containers_raw, containers_error = _safe_get_json(f"{_glances_base_url()}/containers")
    containers_list = containers_raw if isinstance(containers_raw, list) else []
    containers = {
        item.get("name", ""): item
        for item in containers_list
        if isinstance(item, dict)
    }
    return containers, containers_error


def _best_scored_media(items: list[ParsedMedia]) -> ParsedMedia | None:
    if not items:
        return None
    return max(items, key=lambda item: score_candidate(item).tuple)


def _torrent_progress_label(progress: float) -> str:
    return f"{round(progress * 100):.0f}%"


def _postprocessor_candidate_payload(entry: Any) -> dict[str, Any]:
    top_media = _best_scored_media(entry.parsed_files)
    score_summary = score_candidate(top_media).summary if top_media else "-"
    return {
        "name": entry.torrent.name,
        "state": entry.torrent.state or "-",
        "progress_label": _torrent_progress_label(entry.torrent.progress),
        "completed": bool(entry.torrent.completed),
        "score_summary": score_summary,
        "parsed_count": len(entry.parsed_files),
        "unparsed_count": len(entry.unparsed_files),
        "content_root": str(entry.content_root),
    }


def _postprocessor_group_payload(
    *,
    key: Any,
    state: list[Any],
    completed_entries: list[Any],
    reason: str,
    status: str,
) -> dict[str, Any]:
    all_parsed = [item for entry in state for item in entry.parsed_files]
    completed_parsed = [item for entry in completed_entries for item in entry.parsed_files]
    best_overall = _best_scored_media(all_parsed)
    best_completed = _best_scored_media(completed_parsed)
    display_title = (
        best_overall.title
        if best_overall
        else (all_parsed[0].title if all_parsed else key.normalized_title)
    )
    candidates = sorted(
        [_postprocessor_candidate_payload(entry) for entry in state],
        key=lambda item: (
            not item["completed"],
            item["state"],
            item["name"].lower(),
        ),
    )
    return {
        "id": f"{key.normalized_title}-{key.season}-{key.episode}",
        "title": display_title,
        "episode_label": f"S{key.season:02d}E{key.episode:02d}",
        "status": status,
        "reason": reason,
        "candidate_count": len(state),
        "completed_count": len(completed_entries),
        "best_overall": score_candidate(best_overall).summary if best_overall else "-",
        "best_completed": score_candidate(best_completed).summary if best_completed else "-",
        "candidates": candidates,
    }

def _tailscale_status_or_raise(socket_path: str) -> dict[str, Any]:
    status, error = _tailscale_status(socket_path)
    if error or not isinstance(status, dict):
        raise RuntimeError(error or "tailscale status unavailable")
    return status


def _tailscale_localapi_error_message(response: dict[str, Any]) -> str:
    text = str(response.get("text") or "").strip()
    if text:
        return text
    return f"{response.get('status')} {response.get('reason')}"


def _tailscale_start_action(socket_path: str) -> dict[str, Any]:
    _tailscale_patch_prefs(
        socket_path,
        {
            "WantRunning": True,
            "WantRunningSet": True,
        },
    )

    start = _tailscale_localapi_request(socket_path, "POST", "/localapi/v0/start", body={})
    if int(start.get("status", 500)) >= 400:
        raise RuntimeError(_tailscale_localapi_error_message(start))

    time.sleep(1)
    status = _tailscale_status_or_raise(socket_path)
    auth_url = str(status.get("AuthURL") or "").strip()
    backend_state = str(status.get("BackendState") or "")
    if backend_state == "Running" and bool((status.get("Self") or {}).get("Online")):
        return {
            "ok": True,
            "action": "start",
            "message": "Tailscale 已恢复在线。",
        }

    interactive_error: str | None = None
    if backend_state in {"NeedsLogin", "NoState", "Starting"}:
        try:
            login = _tailscale_localapi_request(socket_path, "POST", "/localapi/v0/login-interactive")
            if int(login.get("status", 500)) >= 400:
                interactive_error = _tailscale_localapi_error_message(login)
        except Exception as exc:
            interactive_error = str(exc)

        time.sleep(1)
        status = _tailscale_status_or_raise(socket_path)
        auth_url = str(status.get("AuthURL") or "").strip()
        backend_state = str(status.get("BackendState") or "")

    if auth_url:
        return {
            "ok": True,
            "action": "start",
            "message": "Tailscale 已生成登录链接，请在浏览器里完成授权。",
            "auth_required": True,
            "auth_mode": "browser",
            "auth_url": auth_url,
        }

    if backend_state == "Running" and bool((status.get("Self") or {}).get("Online")):
        return {
            "ok": True,
            "action": "start",
            "message": "Tailscale 已恢复在线。",
        }

    if interactive_error:
        raise RuntimeError(interactive_error)
    return {
        "ok": True,
        "action": "start",
        "message": "Tailscale backend 已开启，但当前版本没有回传登录链接。请在树莓派终端执行 sudo tailscale login 或 sudo tailscale up 完成授权。",
        "auth_required": True,
        "auth_mode": "manual",
    }


def _tailscale_stop_action(socket_path: str) -> dict[str, Any]:
    _tailscale_patch_prefs(
        socket_path,
        {
            "WantRunning": False,
            "WantRunningSet": True,
        },
    )
    return {
        "ok": True,
        "action": "stop",
        "message": "已关闭 Tailscale 网络连接，当前节点授权仍保留，下次可直接重新开启。",
    }


def _tailscale_restart_action(socket_path: str) -> dict[str, Any]:
    _tailscale_stop_action(socket_path)
    time.sleep(1)
    return _tailscale_start_action(socket_path)


def _restart_service_now(target: str) -> dict[str, Any]:
    specs = _service_restart_specs()
    spec = specs.get(target)
    if not spec:
        raise HTTPException(status_code=404, detail=f"unknown restart target: {target}")

    label = str(spec["label"])
    kind = str(spec["kind"])
    if kind == "tailscale":
        result = _tailscale_restart_action(_env("TAILSCALE_SOCKET", "/var/run/tailscale/tailscaled.sock"))
        return {
            "ok": True,
            "target": target,
            "label": label,
            "message": result.get("message") or f"{label} 已重启。",
            "auth_required": bool(result.get("auth_required")),
            "auth_mode": result.get("auth_mode"),
            "auth_url": result.get("auth_url"),
        }

    container_name = str(spec["container_name"])
    _docker_restart_container(container_name)
    return {
        "ok": True,
        "target": target,
        "label": label,
        "message": f"{label} 已发送重启指令。",
    }


def _schedule_homepage_restart(target: str = "homepage") -> dict[str, Any]:
    spec = _service_restart_specs()["homepage"]
    label = str(spec["label"])
    container_name = str(spec["container_name"])

    def runner() -> None:
        time.sleep(1.2)
        try:
            _append_service_control_event(
                level="warning",
                action="restart-service",
                message=f"Restarting {label} container",
                target=target,
                details={"container": container_name},
            )
            _docker_restart_container(container_name)
        except Exception as exc:
            _append_service_control_event(
                level="error",
                action="restart-service",
                message=f"Failed to restart {label}",
                target=target,
                details={"container": container_name, "error": str(exc)},
            )

    _run_background("restart-homepage", runner)
    return {
        "ok": True,
        "scheduled": True,
        "target": target,
        "label": label,
        "reload_after_seconds": 6,
        "message": "已安排 Ops UI 重启，当前页面会短暂断开并自动恢复。",
    }


def _schedule_stack_restart() -> dict[str, Any]:
    targets = _stack_restart_targets()
    specs = _service_restart_specs()

    def runner() -> None:
        for target in targets[:-1]:
            spec = specs[target]
            label = str(spec["label"])
            container_name = str(spec["container_name"])
            try:
                _append_service_control_event(
                    level="warning",
                    action="restart-stack",
                    message=f"Restarting {label}",
                    target=target,
                    details={"container": container_name},
                )
                _docker_restart_container(container_name)
                _append_service_control_event(
                    level="success",
                    action="restart-stack",
                    message=f"Restarted {label}",
                    target=target,
                    details={"container": container_name},
                )
            except Exception as exc:
                _append_service_control_event(
                    level="error",
                    action="restart-stack",
                    message=f"Failed to restart {label}",
                    target=target,
                    details={"container": container_name, "error": str(exc)},
                )
            time.sleep(0.8)

        homepage_spec = specs["homepage"]
        homepage_name = str(homepage_spec["container_name"])
        _append_service_control_event(
            level="warning",
            action="restart-stack",
            message="Restarting Ops UI as the final stack step",
            target="homepage",
            details={"container": homepage_name},
        )
        time.sleep(1.0)
        try:
            _docker_restart_container(homepage_name)
        except Exception as exc:
            _append_service_control_event(
                level="error",
                action="restart-stack",
                message="Failed to restart Ops UI at the final stack step",
                target="homepage",
                details={"container": homepage_name, "error": str(exc)},
            )

    _run_background("restart-compose-stack", runner)
    return {
        "ok": True,
        "scheduled": True,
        "targets": targets,
        "reload_after_seconds": 8,
        "message": "已安排整套服务重启，不包含 Tailscale；Ops UI 会在最后重启。",
    }

def _manual_parsed_media(
    *,
    item: dict[str, Any],
    item_path: Path,
    review_root: Path,
    title: str,
    season: int,
    episode: int,
) -> ParsedMedia:
    parsed = parse_media_file(review_root, item_path)
    release_group = parsed.release_group if isinstance(parsed, ParsedMedia) else None
    return ParsedMedia(
        path=item_path,
        relative_path=item_path.relative_to(review_root),
        title=title.strip(),
        normalized_title=normalize_title(title),
        season=season,
        episode=episode,
        extension=item_path.suffix.lower(),
        release_group=release_group,
    )


def _publish_review_media(media: ParsedMedia, *, review_root: Path) -> dict[str, Any]:
    try:
        result = publish_media(
            source_root=review_root,
            library_root=_library_root(),
            media=media,
        )
    except FileExistsError as exc:
        append_event(
            source="ops-review",
            level="error",
            action="publish",
            message=f"Publish target already exists for {media.title} S{media.season:02d}E{media.episode:02d}",
            details={
                "target": str(build_target_path(_library_root(), media)),
                "error": str(exc),
            },
        )
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return result


def _delete_review_file(item_path: Path, review_root: Path) -> dict[str, Any]:
    size_bytes = item_path.stat().st_size if item_path.exists() else 0
    item_path.unlink()
    _cleanup_empty_dirs(item_path.parent, review_root)
    return {
        "deleted_path": str(item_path),
        "deleted_size_bytes": size_bytes,
        "deleted_size_label": _format_bytes(size_bytes),
    }


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await asyncio.to_thread(_sample_history_once, force=True)
    append_event(
        source="ops-ui",
        level="info",
        action="startup",
        message="Ops UI service started",
        details={
            "refresh_interval_seconds": _refresh_interval_seconds(),
            "log_cap": event_log_cap(),
            "history_file": str(_history_file()),
        },
    )
    sampler_task = asyncio.create_task(_history_sampler_loop())
    try:
        yield
    finally:
        sampler_task.cancel()
        try:
            await sampler_task
        except asyncio.CancelledError:
            pass


router = APIRouter()


async def disable_browser_cache_for_ui_assets(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path in {"/", "/ops-review", "/ops-review/item", "/postprocessor", "/tailscale", "/logs"} or path.startswith("/static/"):
        for header, value in OPS_UI_NO_CACHE_HEADERS.items():
            response.headers[header] = value
    return response


@router.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


@router.get("/api/overview")
def overview(request: Request) -> JSONResponse:
    return JSONResponse(
        build_overview_payload_service(
            locale=resolve_locale(request),
            public_host=_public_host(request),
        )
    )


@router.get("/api/navigation")
def navigation_api(request: Request) -> JSONResponse:
    return JSONResponse(build_navigation_state_service(locale=resolve_locale(request)))


@router.get("/api/manual-review")
def manual_review(request: Request) -> JSONResponse:
    return JSONResponse(build_manual_review_payload_service(locale=resolve_locale(request)))


@router.get("/api/manual-review/item")
def manual_review_item(request: Request, id: str = Query(...)) -> JSONResponse:
    try:
        return JSONResponse(build_manual_review_item_payload_service(id, locale=resolve_locale(request)))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="manual review file not found") from exc


@router.get("/api/logs")
def logs_api(
    request: Request,
    level: str | None = Query(default=None),
    source: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=300, ge=20, le=1500),
) -> JSONResponse:
    return JSONResponse(build_logs_payload_service(level=level, source=source, search=q, limit=limit, locale=resolve_locale(request)))


@router.get("/api/tailscale")
def tailscale_api(request: Request) -> JSONResponse:
    return JSONResponse(build_tailscale_payload_service(locale=resolve_locale(request)))


@router.get("/api/postprocessor")
def postprocessor_api(request: Request) -> JSONResponse:
    return JSONResponse(build_postprocessor_payload_service(locale=resolve_locale(request)))


@router.post("/api/tailscale/action")
def tailscale_action_api(payload: TailscaleActionRequest) -> JSONResponse:
    socket_path = _env("TAILSCALE_SOCKET", "/var/run/tailscale/tailscaled.sock")
    action = payload.action

    try:
        if action == "start":
            result = _tailscale_start_action(socket_path)
            append_event(
                source="tailscale",
                level="warning",
                action="start",
                message="Triggered Tailscale start flow from Ops UI",
                details={
                    "auth_url": result.get("auth_url"),
                },
            )
            return JSONResponse(result)

        result = _tailscale_stop_action(socket_path)
        append_event(
            source="tailscale",
            level="warning",
            action="stop",
            message="Triggered Tailscale stop flow from Ops UI",
        )
        return JSONResponse(result)
    except RuntimeError as exc:
        append_event(
            source="tailscale",
            level="error",
            action=action,
            message=f"Tailscale action failed: {action}",
            details={
                "error": str(exc),
            },
        )
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/services/restart")
def restart_service_api(payload: ServiceRestartRequest) -> JSONResponse:
    target = payload.target.strip().lower()
    specs = _service_restart_specs()
    if target not in specs:
        raise HTTPException(status_code=404, detail=f"unknown restart target: {target}")

    if target == "homepage":
        _append_service_control_event(
            level="warning",
            action="restart-service",
            message="Scheduled Ops UI restart from dashboard",
            target=target,
        )
        return JSONResponse(_schedule_homepage_restart(target=target))

    try:
        result = _restart_service_now(target)
        _append_service_control_event(
            level="success",
            action="restart-service",
            message=f"Restarted {result['label']}",
            target=target,
            details={"auth_url": result.get("auth_url")},
        )
        return JSONResponse(result)
    except HTTPException:
        raise
    except Exception as exc:
        _append_service_control_event(
            level="error",
            action="restart-service",
            message=f"Failed to restart {specs[target]['label']}",
            target=target,
            details={"error": str(exc)},
        )
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/services/restart-all")
def restart_all_services_api() -> JSONResponse:
    _append_service_control_event(
        level="warning",
        action="restart-stack",
        message="Scheduled compose stack restart from dashboard",
        target="stack",
        details={"targets": _stack_restart_targets()},
    )
    return JSONResponse(_schedule_stack_restart())


@router.post("/api/logs/clear")
def clear_logs_api() -> JSONResponse:
    result = clear_events()
    append_event(
        source="ops-ui",
        level="warning",
        action="clear-logs",
        message="Structured event log was cleared from the Logs workspace",
        details={
            "cleared": result["cleared"],
        },
    )
    return JSONResponse(
        {
            "ok": True,
            "message": f"已清理结构化日志，清除 {result['cleared']} 条旧记录。",
            "cleared": result["cleared"],
        }
    )


@router.post("/api/manual-review/item/retry-parse")
def manual_review_retry_parse(id: str = Query(...)) -> JSONResponse:
    item, item_path, review_root = _manual_review_item_or_404(id)
    auto_parse = _build_auto_parse_payload(item_path, review_root)
    parsed = auto_parse.get("parsed")
    if auto_parse.get("status") != "parsed" or not isinstance(parsed, dict):
        raise HTTPException(
            status_code=422,
            detail=auto_parse.get("reason") or "file is still not parseable",
        )

    media = _manual_parsed_media(
        item=item,
        item_path=item_path,
        review_root=review_root,
        title=parsed["title"],
        season=int(parsed["season"]),
        episode=int(parsed["episode"]),
    )
    result = _publish_review_media(media, review_root=review_root)
    append_event(
        source="ops-review",
        level="success",
        action="retry-parse",
        message=f"Published from retry parse: {media.title} S{media.season:02d}E{media.episode:02d}",
        details={
            "source": str(media.relative_path),
            "target": result["target"],
        },
    )
    return JSONResponse(
        {
            "ok": True,
            "action": "retry-parse",
            "message": f"已按自动解析结果发布到 Seasonal: {media.title} S{media.season:02d}E{media.episode:02d}",
            "result": result,
        }
    )


@router.post("/api/manual-review/item/publish")
def manual_review_publish(
    payload: ManualPublishRequest,
    id: str = Query(...),
) -> JSONResponse:
    item, item_path, review_root = _manual_review_item_or_404(id)
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="title is required")

    media = _manual_parsed_media(
        item=item,
        item_path=item_path,
        review_root=review_root,
        title=title,
        season=payload.season,
        episode=payload.episode,
    )
    result = _publish_review_media(media, review_root=review_root)
    append_event(
        source="ops-review",
        level="success",
        action="manual-publish",
        message=f"Manually published {title} S{payload.season:02d}E{payload.episode:02d}",
        details={
            "source": str(media.relative_path),
            "target": result["target"],
        },
    )
    return JSONResponse(
        {
            "ok": True,
            "action": "publish",
            "message": f"已手动发布到 Seasonal: {title} S{payload.season:02d}E{payload.episode:02d}",
            "result": result,
        }
    )


@router.post("/api/manual-review/item/delete")
def manual_review_delete(id: str = Query(...)) -> JSONResponse:
    item, item_path, review_root = _manual_review_item_or_404(id)
    result = _delete_review_file(item_path, review_root)
    append_event(
        source="ops-review",
        level="warning",
        action="delete",
        message=f"Deleted manual review file: {item['filename']}",
        details={
            "relative_path": item["relative_path"],
            "size": result["deleted_size_label"],
        },
    )
    return JSONResponse(
        {
            "ok": True,
            "action": "delete",
            "message": f"已从人工审核队列删除: {item['filename']}",
            "result": result,
        }
    )


@router.get("/")
def index(request: Request):
    template_name, page_key, title = PAGE_TEMPLATES["/"]
    return render_page(request, template_name, page_key, title)


@router.get("/ops-review")
def ops_review_placeholder(request: Request):
    template_name, page_key, title = PAGE_TEMPLATES["/ops-review"]
    return render_page(request, template_name, page_key, title)


@router.get("/ops-review/item")
def ops_review_item_page(request: Request):
    template_name, page_key, title = PAGE_TEMPLATES["/ops-review/item"]
    return render_page(request, template_name, page_key, title)


@router.get("/postprocessor")
def postprocessor_page(request: Request):
    template_name, page_key, title = PAGE_TEMPLATES["/postprocessor"]
    return render_page(request, template_name, page_key, title)


@router.get("/tailscale")
def tailscale_page(request: Request):
    template_name, page_key, title = PAGE_TEMPLATES["/tailscale"]
    return render_page(request, template_name, page_key, title)


@router.get("/logs")
def logs_placeholder(request: Request):
    template_name, page_key, title = PAGE_TEMPLATES["/logs"]
    return render_page(request, template_name, page_key, title)


def create_app(*, enable_lifespan: bool = True) -> FastAPI:
    app = FastAPI(title="Anime Ops UI", lifespan=lifespan if enable_lifespan else None)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(router)
    app.include_router(mobile_auth_router)
    app.include_router(mobile_home_router)
    app.include_router(mobile_items_router)
    app.include_router(mobile_me_router)
    app.middleware("http")(disable_browser_cache_for_ui_assets)
    return app


def main() -> None:
    import uvicorn

    uvicorn.run(create_app(), host="0.0.0.0", port=3000)


if __name__ == "__main__":
    main()
