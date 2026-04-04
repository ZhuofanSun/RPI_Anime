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

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
REPO_ROOT = APP_DIR.parents[3]
POSTPROCESSOR_SRC = REPO_ROOT / "services" / "postprocessor" / "src"
if POSTPROCESSOR_SRC.exists() and str(POSTPROCESSOR_SRC) not in sys.path:
    sys.path.insert(0, str(POSTPROCESSOR_SRC))

from anime_postprocessor.models import ParsedMedia, UnparsedMedia
from anime_postprocessor.eventlog import append_event, clear_events, event_log_cap, event_log_path, read_events
from anime_postprocessor.parser import normalize_title, parse_media_file
from anime_postprocessor.publisher import build_target_path, publish_media
from anime_postprocessor.qb import QBClient
from anime_postprocessor.selector import score_candidate
from anime_postprocessor.watch import _build_groups, _should_process_group

MEDIA_EXTENSIONS = {".mkv", ".mp4", ".avi", ".m4v", ".ts"}
HISTORY_LOCK = threading.Lock()
HISTORY_SERIES = ("cpu_percent", "cpu_temp_c", "playback_tx_rate")
HISTORY_STATE: dict[str, Any] | None = None


class ManualPublishRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    season: int = Field(..., ge=1, le=99)
    episode: int = Field(..., ge=1, le=999)


class TailscaleActionRequest(BaseModel):
    action: str = Field(..., pattern="^(start|stop)$")


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


def _format_uptime(value: str | None) -> str:
    if not value:
        return "-"
    parts = value.split(":")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        hours, minutes, _seconds = [int(part) for part in parts]
        if hours >= 24:
            days, rem_hours = divmod(hours, 24)
            return f"{days}d {rem_hours}h {minutes}m"
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


def _container_status_count(containers: dict[str, dict[str, Any]]) -> tuple[int, int]:
    values = list(containers.values())
    running_like = sum(1 for item in values if str(item.get("status", "")).lower() == "running")
    return running_like, len(values)


def _glances_base_url() -> str:
    return _env("GLANCES_API_URL", "http://glances:61208/api/4").rstrip("/")


def _refresh_interval_seconds() -> int:
    return max(4, _env_int("OPS_UI_REFRESH_INTERVAL_SECONDS", 8))


def _sample_interval_seconds() -> int:
    return max(30, _env_int("OPS_UI_SAMPLE_INTERVAL_SECONDS", 60))


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
    containers_list = containers_raw if isinstance(containers_raw, list) else []
    containers = {
        item.get("name", ""): item
        for item in containers_list
        if isinstance(item, dict)
    }
    jellyfin = containers.get("jellyfin", {})
    jellyfin_network = jellyfin.get("network", {}) if isinstance(jellyfin, dict) else {}
    return {
        "cpu_percent": (quicklook or {}).get("cpu") if isinstance(quicklook, dict) else None,
        "cpu_temp_c": _extract_temperature(sensors),
        "playback_tx_rate": float(jellyfin.get("network_tx") or jellyfin_network.get("tx") or 0.0),
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
    def __init__(self, unix_socket_path: str, timeout: int) -> None:
        super().__init__("local-tailscaled.sock", timeout=timeout)
        self.unix_socket_path = unix_socket_path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.unix_socket_path)


def _tailscale_localapi_request(
    socket_path: str,
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    timeout: int = 5,
) -> dict[str, Any]:
    try:
        connection = UnixHTTPConnection(socket_path, timeout=5)
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Host": "local-tailscaled.sock", "Sec-Tailscale": "localapi"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(payload))
        connection.request(method, path, body=payload, headers=headers)
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
    manual_review_count: int,
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
            "name": "Jellyfin",
            "href": _service_link(base_host, int(_env("JELLYFIN_PORT", "8096"))),
            "description": "私人影音库与播放入口",
            "status": containers.get("jellyfin", {}).get("status", "unknown"),
            "meta": "Media server",
            "uptime": container_uptime("jellyfin"),
        },
        {
            "name": "qBittorrent",
            "href": _service_link(base_host, int(_env("QBITTORRENT_WEBUI_PORT", "8080"))),
            "description": "下载、任务队列和分类",
            "status": containers.get("qbittorrent", {}).get("status", "unknown"),
            "meta": "Download client",
            "uptime": container_uptime("qbittorrent"),
        },
        {
            "name": "AutoBangumi",
            "href": _service_link(base_host, int(_env("AUTOBANGUMI_PORT", "7892"))),
            "description": "RSS 订阅、规则和自动投递",
            "status": containers.get("autobangumi", {}).get("status", "unknown"),
            "meta": "Subscription",
            "uptime": container_uptime("autobangumi"),
        },
        {
            "name": "Glances",
            "href": _service_link(base_host, int(_env("GLANCES_PORT", "61208"))),
            "description": "更细的系统、容器和进程监控页",
            "status": containers.get("glances", {}).get("status", "unknown"),
            "meta": "System monitor",
            "uptime": container_uptime("glances"),
        },
        {
            "name": "Postprocessor",
            "href": f"{ops_ui_base}/postprocessor",
            "description": "下载完成后的选优、发布和 NFO 生成",
            "status": containers.get("anime-postprocessor", {}).get("status", "unknown"),
            "meta": "Background worker",
            "uptime": container_uptime("anime-postprocessor"),
            "internal": True,
        },
        {
            "name": "Ops Review",
            "href": f"{ops_ui_base}/ops-review",
            "description": "人工审核队列、详情页和受控文件动作",
            "status": "online",
            "meta": f"{manual_review_count} files",
            "uptime": "Review workspace",
            "internal": True,
        },
        {
            "name": "Logs",
            "href": f"{ops_ui_base}/logs",
            "description": "结构化事件日志、来源筛选、等级着色与清理",
            "status": "online",
            "meta": f"{log_count} events",
            "uptime": f"cap {event_log_cap()}",
            "internal": True,
        },
        {
            "name": "Tailscale",
            "href": f"{ops_ui_base}/tailscale",
            "description": "本地 tailnet 状态与远程访问链路",
            "status": tailscale_state,
            "meta": _tailscale_ip_pair(tailscale_self.get("TailscaleIPs") if tailscale_self else None)[0],
            "uptime": _strip_trailing_dot(tailscale_self.get("DNSName")) if tailscale_self else None,
            "internal": True,
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
    payload = build_manual_review_item_payload(item_id)
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


def build_manual_review_payload() -> dict[str, Any]:
    review_root = _manual_review_root()
    items = _manual_review_items(review_root)
    bucket_stats: dict[str, dict[str, Any]] = {}
    total_bytes = 0
    series_names: set[str] = set()

    for item in items:
        total_bytes += int(item["size_bytes"])
        series_names.add(item["series_name"])
        stats = bucket_stats.setdefault(
            item["bucket"],
            {"bucket": item["bucket"], "count": 0, "size_bytes": 0},
        )
        stats["count"] += 1
        stats["size_bytes"] += int(item["size_bytes"])

    buckets = [
        {
            "bucket": bucket,
            "label": bucket.replace("_", " ").title(),
            "count": stats["count"],
            "size_bytes": stats["size_bytes"],
            "size_label": _format_bytes(stats["size_bytes"]),
        }
        for bucket, stats in sorted(bucket_stats.items(), key=lambda entry: (-entry[1]["count"], entry[0]))
    ]

    summary_cards = [
        {
            "label": "Review Files",
            "value": str(len(items)),
            "detail": "pending media files",
        },
        {
            "label": "Total Size",
            "value": _format_bytes(total_bytes),
            "detail": str(review_root),
        },
        {
            "label": "Series",
            "value": str(len(series_names)),
            "detail": "distinct folders",
        },
        {
            "label": "Buckets",
            "value": str(len(buckets)),
            "detail": ", ".join(bucket["label"] for bucket in buckets[:3]) if buckets else "no review buckets",
        },
    ]

    return {
        "title": "Ops Review",
        "subtitle": "人工审核队列与未自动入库文件清单",
        "refresh_interval_seconds": 15,
        "root": str(review_root),
        "summary_cards": summary_cards,
        "buckets": buckets,
        "items": items,
        "total_files": len(items),
        "total_size_bytes": total_bytes,
        "total_size_label": _format_bytes(total_bytes),
        "last_updated": datetime.now().isoformat(timespec="seconds"),
    }


def build_logs_payload(
    *,
    level: str | None = None,
    source: str | None = None,
    search: str | None = None,
    limit: int = 300,
) -> dict[str, Any]:
    raw_events = read_events()
    keyword = (search or "").strip().lower()
    filtered = []
    for item in raw_events:
        if level and item.get("level") != level:
            continue
        if source and item.get("source") != source:
            continue
        if keyword:
            haystack = " ".join(
                [
                    str(item.get("source", "")),
                    str(item.get("level", "")),
                    str(item.get("action", "")),
                    str(item.get("message", "")),
                    json.dumps(item.get("details", {}), ensure_ascii=False),
                ]
            ).lower()
            if keyword not in haystack:
                continue
        filtered.append(item)

    visible = filtered[: max(20, min(limit, event_log_cap()))]
    levels = sorted({str(item.get("level", "info")) for item in raw_events})
    sources = sorted({str(item.get("source", "unknown")) for item in raw_events})
    level_counts: dict[str, int] = {}
    for item in raw_events:
        item_level = str(item.get("level", "info"))
        level_counts[item_level] = level_counts.get(item_level, 0) + 1

    summary_cards = [
        {
            "label": "Visible",
            "value": str(len(visible)),
            "detail": f"{len(filtered)} matched / {len(raw_events)} total",
        },
        {
            "label": "Sources",
            "value": str(len(sources)),
            "detail": ", ".join(sources[:3]) if sources else "no sources yet",
        },
        {
            "label": "Errors",
            "value": str(level_counts.get("error", 0)),
            "detail": f"{level_counts.get('warning', 0)} warnings",
        },
        {
            "label": "Retention",
            "value": str(event_log_cap()),
            "detail": str(event_log_path()),
        },
    ]

    return {
        "title": "Logs",
        "subtitle": "项目侧结构化事件日志，优先覆盖自动处理、人工审核与运维动作。",
        "refresh_interval_seconds": 10,
        "summary_cards": summary_cards,
        "levels": levels,
        "sources": sources,
        "items": visible,
        "total_count": len(raw_events),
        "matched_count": len(filtered),
        "retention_cap": event_log_cap(),
        "storage_path": str(event_log_path()),
        "last_updated": datetime.now().isoformat(timespec="seconds"),
    }


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


def build_postprocessor_payload() -> dict[str, Any]:
    paths = _postprocessor_paths()
    source_root = paths["source_root"]
    target_root = paths["target_root"]
    review_root = paths["review_root"]
    title_map = paths["title_map"]
    category = _env("POSTPROCESSOR_CATEGORY", "Bangumi")
    poll_interval = _env_int("POSTPROCESSOR_POLL_INTERVAL", 60)
    wait_timeout = _env_int("POSTPROCESSOR_WAIT_TIMEOUT", 1800)
    delete_losers = _env("POSTPROCESSOR_DELETE_LOSERS", "true").lower() in {"1", "true", "yes", "on"}

    containers, containers_error = _glances_containers_snapshot()
    worker = containers.get("anime-postprocessor", {})
    worker_status = worker.get("status", "unknown") if isinstance(worker, dict) else "unknown"
    worker_uptime = worker.get("uptime") if isinstance(worker, dict) else None

    qb_snapshot, qb_error = _qb_snapshot()
    diagnostics: list[dict[str, Any]] = []
    if containers_error:
        diagnostics.append({"source": "glances/containers", "message": containers_error})
    if qb_error:
        diagnostics.append({"source": "qbittorrent", "message": qb_error})

    ready_groups: list[dict[str, Any]] = []
    waiting_groups: list[dict[str, Any]] = []
    active_groups: list[dict[str, Any]] = []
    unparsed_torrents: list[dict[str, Any]] = []
    total_groups = 0

    if qb_error is None:
        try:
            qb = QBClient(
                _env("QBITTORRENT_API_URL", "http://qbittorrent:8080"),
                _env("QBITTORRENT_USERNAME", ""),
                _env("QBITTORRENT_PASSWORD", ""),
            )
            qb.auth()
            torrents = qb.list_torrents(category=category)
            groups, completed_unparsed = _build_groups(
                torrents,
                qb,
                qb_download_root=Path(_env("QBITTORRENT_DOWNLOAD_ROOT", "/downloads/Bangumi")),
                local_download_root=source_root,
            )
            total_groups = len(groups)
            now_ts = int(time.time())
            for key, state in sorted(
                groups.items(),
                key=lambda item: (item[0].normalized_title, item[0].season, item[0].episode),
            ):
                completed_entries = [entry for entry in state if entry.torrent.completed]
                should_process, reason = _should_process_group(
                    state=state,
                    completed_entries=completed_entries,
                    now_ts=now_ts,
                    wait_timeout=wait_timeout,
                )
                if should_process:
                    ready_groups.append(
                        _postprocessor_group_payload(
                            key=key,
                            state=state,
                            completed_entries=completed_entries,
                            reason=reason,
                            status="ready",
                        )
                    )
                elif completed_entries:
                    waiting_groups.append(
                        _postprocessor_group_payload(
                            key=key,
                            state=state,
                            completed_entries=completed_entries,
                            reason=reason,
                            status="waiting",
                        )
                    )
                else:
                    active_groups.append(
                        _postprocessor_group_payload(
                            key=key,
                            state=state,
                            completed_entries=completed_entries,
                            reason=reason,
                            status="active",
                        )
                    )

            for entry in completed_unparsed:
                unparsed_torrents.append(
                    {
                        "title": entry.torrent.name,
                        "status": "review",
                        "reason": "已完成但无法解析，下一轮会送入 manual_review",
                        "media_count": len(entry.media_paths),
                        "path": str(entry.content_root),
                    }
                )
        except Exception as exc:
            diagnostics.append({"source": "postprocessor", "message": str(exc)})

    post_events = [
        item
        for item in read_events(limit=200)
        if str(item.get("source")) == "postprocessor"
    ][:12]

    summary_cards = [
        {
            "label": "Worker",
            "value": str(worker_status).title(),
            "detail": worker_uptime or "container uptime unavailable",
        },
        {
            "label": "Episode Groups",
            "value": str(total_groups),
            "detail": f"{len(ready_groups)} ready · {len(waiting_groups)} waiting",
        },
        {
            "label": "Queue Tasks",
            "value": str((qb_snapshot or {}).get("task_count", "-")) if qb_snapshot else "-",
            "detail": f"{(qb_snapshot or {}).get('active_downloads', 0)} downloading · {(qb_snapshot or {}).get('active_seeds', 0)} seeding" if qb_snapshot else "qB unavailable",
        },
        {
            "label": "Manual Review",
            "value": str(_count_media_files(review_root)),
            "detail": f"{len(unparsed_torrents)} completed-unparsed pending",
        },
    ]

    config_cards = [
        {
            "label": "Source Root",
            "value": str(source_root),
            "detail": "download staging",
        },
        {
            "label": "Target Root",
            "value": str(target_root),
            "detail": "Jellyfin seasonal library",
        },
        {
            "label": "Review Root",
            "value": str(review_root),
            "detail": "manual review queue",
        },
        {
            "label": "Policy",
            "value": category,
            "detail": f"poll {poll_interval}s · wait {wait_timeout}s · delete losers {'on' if delete_losers else 'off'}",
        },
        {
            "label": "Title Map",
            "value": str(title_map),
            "detail": "series rename / season offset",
        },
    ]

    commands = [
        {
            "label": "Watch Once",
            "description": "手动触发一轮 watch 逻辑，最接近常驻服务实际行为。",
            "command": "docker compose --env-file deploy/.env -f deploy/compose.yaml run --rm postprocessor watch --once",
        },
        {
            "label": "Publish Dry Run",
            "description": "查看当前下载区如果手动发布，会生成什么计划。",
            "command": "docker compose --env-file deploy/.env -f deploy/compose.yaml run --rm postprocessor publish",
        },
        {
            "label": "Live Logs",
            "description": "持续观察常驻 worker 当前每轮处理输出。",
            "command": "docker compose --env-file deploy/.env -f deploy/compose.yaml logs -f postprocessor",
        },
    ]

    return {
        "title": "Postprocessor",
        "subtitle": "下载完成后的选优、等待窗口、自动发布与 review 分流工作台。",
        "refresh_interval_seconds": 15,
        "summary_cards": summary_cards,
        "config_cards": config_cards,
        "commands": commands,
        "recent_events": post_events,
        "sections": [
            {
                "id": "ready",
                "title": "Ready On Next Tick",
                "description": "已经满足处理条件，下一轮 watch 会直接接管并发布。",
                "meta": f"{len(ready_groups)} groups",
                "items": ready_groups[:8],
            },
            {
                "id": "waiting",
                "title": "Waiting Window",
                "description": "已有完成候选，但还在给更高优先级版本留补完窗口。",
                "meta": f"{len(waiting_groups)} groups",
                "items": waiting_groups[:8],
            },
            {
                "id": "active",
                "title": "Active Downloads",
                "description": "当前还没有任何完成候选，继续等待下载完成。",
                "meta": f"{len(active_groups)} groups",
                "items": active_groups[:8],
            },
            {
                "id": "unparsed",
                "title": "Completed But Unparsed",
                "description": "已完成但无法解析的 torrent，下一轮会被送进 manual_review。",
                "meta": f"{len(unparsed_torrents)} torrents",
                "items": unparsed_torrents[:8],
            },
        ],
        "diagnostics": diagnostics,
        "last_updated": datetime.now().isoformat(timespec="seconds"),
    }


def build_tailscale_payload() -> dict[str, Any]:
    base_host = _env("HOMEPAGE_BASE_HOST", socket.gethostname())
    tailscale_socket = _env("TAILSCALE_SOCKET", "/var/run/tailscale/tailscaled.sock")
    tailscale, tailscale_error = _tailscale_status(tailscale_socket)
    prefs, prefs_error = _tailscale_prefs(tailscale_socket)
    self_info = ((tailscale or {}).get("Self") or {}) if isinstance(tailscale, dict) else {}
    peer_map = ((tailscale or {}).get("Peer") or {}) if isinstance(tailscale, dict) else {}
    peer_values = list(peer_map.values()) if isinstance(peer_map, dict) else []
    backend_state = (tailscale or {}).get("BackendState", "unavailable") if tailscale else "unavailable"
    health_messages = list((tailscale or {}).get("Health", [])) if isinstance(tailscale, dict) else []
    online_peer_count = sum(1 for peer in peer_values if peer.get("Online"))
    exit_node_candidates = sum(1 for peer in peer_values if peer.get("ExitNodeOption"))
    tail_ip, ipv6 = _tailscale_ip_pair(self_info.get("TailscaleIPs") if self_info else None)
    dns_name = _strip_trailing_dot(self_info.get("DNSName"))
    self_online = bool(self_info.get("Online"))
    want_running = bool((prefs or {}).get("WantRunning")) if isinstance(prefs, dict) else backend_state == "Running"
    reachability = "Online" if self_online else ("Stopped" if not want_running else "Offline")
    logged_out = bool((prefs or {}).get("LoggedOut")) if isinstance(prefs, dict) else backend_state in {"NeedsLogin", "NoState"}
    machinekey_error = any("machinekey" in str(message).lower() for message in health_messages)
    control_action = "stop" if want_running else "start"
    control_label = "关闭 Tailscale" if control_action == "stop" else "开启 Tailscale"
    if control_action == "stop":
        control_detail = "仅停止 tailnet 连接，保留当前节点授权与配置。"
    elif machinekey_error:
        control_detail = "当前本地 state 已损坏，需要先重建宿主机 Tailscale 状态。"
    elif backend_state in {"NeedsLogin", "NoState"} or logged_out:
        control_detail = "启动 backend 后会进入登录态，需要在树莓派终端或网页登录完成授权。"
    else:
        control_detail = "恢复 tailnet backend 与远程访问链路。"
    if self_online:
        self_note = "当前节点已在线，可通过 Tailscale IP 或 MagicDNS 从其他设备访问。"
    elif machinekey_error:
        self_note = "当前节点的本地 state 已损坏。请先完整重建 /var/lib/tailscale，然后再重新登录。"
    elif backend_state in {"NeedsLogin", "NoState"} or logged_out:
        self_note = "当前节点已经脱离 tailnet，会话需要重新登录后才能恢复。"
    elif not want_running:
        self_note = "当前节点已关闭 Tailscale 网络连接，但授权仍保留，可随时重新开启。"
    else:
        self_note = "后台进程仍在运行，但控制面或 peer 可达性异常，节点当前不可用。"

    summary_cards = [
        {
            "label": "Backend",
            "value": backend_state,
            "detail": "local socket only",
        },
        {
            "label": "Reachability",
            "value": reachability,
            "detail": "coordination + peer connectivity",
        },
        {
            "label": "Peers",
            "value": str(len(peer_values)),
            "detail": f"{online_peer_count} online · {exit_node_candidates} exit-node capable",
        },
        {
            "label": "Tailnet IP",
            "value": tail_ip,
            "detail": dns_name,
        },
    ]

    self_cards = [
        {
            "label": "Host",
            "value": self_info.get("HostName") or base_host,
            "detail": dns_name,
        },
        {
            "label": "Reachability",
            "value": "Yes" if self_online else "No",
            "detail": "tailnet reachable" if self_online else "currently unreachable from tailnet",
        },
        {
            "label": "IPv4",
            "value": tail_ip,
            "detail": "primary tailnet address",
        },
        {
            "label": "IPv6",
            "value": ipv6,
            "detail": "secondary tailnet address",
        },
        {
            "label": "Current Addr",
            "value": self_info.get("CurAddr") or "-",
            "detail": f"relay {self_info.get('Relay') or '-'}",
        },
        {
            "label": "Traffic",
            "value": f"{_format_bytes(self_info.get('RxBytes'))} ↓",
            "detail": f"{_format_bytes(self_info.get('TxBytes'))} ↑",
        },
    ]

    peers = [
        {
            "id": peer.get("PublicKey") or str(peer.get("ID") or peer.get("HostName") or "peer"),
            "host_name": peer.get("HostName", "Unknown"),
            "dns_name": _strip_trailing_dot(peer.get("DNSName")),
            "ip": _tailscale_ip_pair(peer.get("TailscaleIPs"))[0],
            "ipv6": _tailscale_ip_pair(peer.get("TailscaleIPs"))[1],
            "os": peer.get("OS", "-"),
            "online": bool(peer.get("Online")),
            "active": bool(peer.get("Active")),
            "status": "online" if peer.get("Online") else "offline",
            "current_addr": peer.get("CurAddr") or "-",
            "relay": peer.get("Relay") or "-",
            "rx_label": _format_bytes(peer.get("RxBytes")),
            "tx_label": _format_bytes(peer.get("TxBytes")),
            "last_write_label": _format_iso_datetime(peer.get("LastWrite")),
            "last_seen_label": _format_iso_datetime(peer.get("LastSeen")),
            "last_handshake_label": _format_iso_datetime(peer.get("LastHandshake")),
            "key_expiry_label": _format_iso_datetime(peer.get("KeyExpiry")),
            "exit_node_option": bool(peer.get("ExitNodeOption")),
            "exit_node": bool(peer.get("ExitNode")),
        }
        for peer in sorted(
            peer_values,
            key=lambda item: (
                not bool(item.get("Online")),
                not bool(item.get("Active")),
                str(item.get("HostName", "")).lower(),
            ),
        )
    ]

    diagnostics = []
    if tailscale_error:
        diagnostics.append(
            {
                "source": "tailscale-localapi",
                "message": tailscale_error,
            }
        )
    if prefs_error:
        diagnostics.append(
            {
                "source": "tailscale-prefs",
                "message": prefs_error,
            }
        )
    diagnostics.extend(
        {
            "source": "tailscale-health",
            "message": message,
        }
        for message in health_messages
    )

    return {
        "title": "Tailscale",
        "subtitle": "本地 tailnet 状态、peer 列表和节点可达性诊断。",
        "refresh_interval_seconds": 15,
        "socket_path": tailscale_socket,
        "summary_cards": summary_cards,
        "self_cards": self_cards,
        "self_note": self_note,
        "peers": peers,
        "peer_total": len(peers),
        "peer_online": online_peer_count,
        "backend_state": backend_state,
        "reachability": reachability,
        "want_running": want_running,
        "logged_out": logged_out,
        "machinekey_error": machinekey_error,
        "control": {
            "action": control_action,
            "label": control_label,
            "detail": control_detail,
        },
        "self": {
            "host_name": self_info.get("HostName") or _env("HOMEPAGE_BASE_HOST", socket.gethostname()),
            "dns_name": dns_name,
            "tail_ip": tail_ip,
            "os": self_info.get("OS", "-"),
            "key_expiry_label": _format_iso_datetime(self_info.get("KeyExpiry")),
            "relay": self_info.get("Relay") or "-",
            "current_addr": self_info.get("CurAddr") or "-",
        },
        "diagnostics": diagnostics,
        "last_updated": datetime.now().isoformat(timespec="seconds"),
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


def build_manual_review_item_payload(item_id: str) -> dict[str, Any]:
    review_root = _manual_review_root()
    items = _manual_review_items(review_root)
    item = next((entry for entry in items if entry["id"] == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="manual review item not found")

    item_path = review_root / item["relative_path"]
    parent_dir = item_path.parent
    sibling_items: list[dict[str, Any]] = []
    if parent_dir.exists():
        for sibling in sorted(parent_dir.iterdir()):
            if sibling.is_file() and sibling.suffix.lower() in MEDIA_EXTENSIONS:
                sibling_item = _review_item_from_path(sibling, review_root)
                sibling_items.append(
                    {
                        "id": sibling_item["id"],
                        "filename": sibling_item["filename"],
                        "size_label": sibling_item["size_label"],
                        "modified_label": sibling_item["modified_label"],
                        "is_current": sibling_item["id"] == item_id,
                    }
                )

    auto_parse = _build_auto_parse_payload(item_path, review_root)
    manual_defaults = _manual_publish_defaults(item, auto_parse)

    return {
        "title": "Review Item",
        "subtitle": item["series_name"],
        "refresh_interval_seconds": 15,
        "root": str(review_root),
        "item": item,
        "siblings": sibling_items,
        "auto_parse": auto_parse,
        "manual_publish_defaults": manual_defaults,
        "breadcrumbs": [
            {"label": "Dashboard", "href": "/"},
            {"label": "Ops Review", "href": "/ops-review"},
            {"label": item["filename"], "href": None},
        ],
        "last_updated": datetime.now().isoformat(timespec="seconds"),
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


def build_overview() -> dict[str, Any]:
    try:
        _sample_history_once()
    except Exception:
        pass

    anime_data_root = Path(_env("ANIME_DATA_ROOT", "/srv/anime-data"))
    base_host = _env("HOMEPAGE_BASE_HOST", socket.gethostname())
    glances_base = _glances_base_url()
    disk = _disk_snapshot(anime_data_root)

    quicklook, quicklook_error = _safe_get_json(f"{glances_base}/quicklook")
    containers_raw, containers_error = _safe_get_json(f"{glances_base}/containers")
    mem, mem_error = _safe_get_json(f"{glances_base}/mem")
    uptime_raw, uptime_error = _safe_get_json(f"{glances_base}/uptime")
    load_raw, load_error = _safe_get_json(f"{glances_base}/load")
    sensors_raw, sensors_error = _safe_get_json(f"{glances_base}/sensors")
    tailscale_socket = _env("TAILSCALE_SOCKET", "/var/run/tailscale/tailscaled.sock")
    tailscale, tailscale_error = _tailscale_status(tailscale_socket)
    qb, qb_error = _qb_snapshot()

    containers_list = containers_raw if isinstance(containers_raw, list) else []
    containers = {
        item.get("name", ""): item
        for item in containers_list
        if isinstance(item, dict)
    }

    manual_review_root = anime_data_root / "processing" / "manual_review"
    seasonal_root = anime_data_root / "library" / "seasonal"
    downloads_root = anime_data_root / "downloads" / "Bangumi"

    tailscale_self = ((tailscale or {}).get("Self") or {}) if isinstance(tailscale, dict) else {}
    tailscale_peers = ((tailscale or {}).get("Peer") or {}) if isinstance(tailscale, dict) else {}
    tailscale_peer_values = list(tailscale_peers.values()) if isinstance(tailscale_peers, dict) else []
    tailnet_online_peers = sum(1 for peer in tailscale_peer_values if peer.get("Online"))
    running_services, total_services = _container_status_count(containers)
    cpu_percent = (quicklook or {}).get("cpu") if isinstance(quicklook, dict) else None
    memory_percent = (mem or {}).get("percent") if isinstance(mem, dict) else None
    cpu_temp_c = _extract_temperature(sensors_raw)
    jellyfin_container = containers.get("jellyfin", {})
    jellyfin_network = jellyfin_container.get("network", {}) if isinstance(jellyfin_container, dict) else {}
    playback_tx_rate = jellyfin_container.get("network_tx") or jellyfin_network.get("tx")
    host_uptime = _format_uptime(uptime_raw if isinstance(uptime_raw, str) else None)
    load_min1 = (load_raw or {}).get("min1") if isinstance(load_raw, dict) else None
    load_min5 = (load_raw or {}).get("min5") if isinstance(load_raw, dict) else None
    load_min15 = (load_raw or {}).get("min15") if isinstance(load_raw, dict) else None
    load_detail = "-"
    if all(value is not None for value in (load_min1, load_min5, load_min15)):
        load_detail = f"{float(load_min1):.2f} / {float(load_min5):.2f} / {float(load_min15):.2f}"

    trend_window_hours = _series_window_hours()
    upload_window_days = _upload_window_days()
    cpu_values, cpu_points = _series_values("cpu_percent", window_hours=trend_window_hours)
    temp_values, temp_points = _series_values("cpu_temp_c", window_hours=trend_window_hours)
    playback_values, playback_points = _series_values("playback_tx_rate", window_hours=trend_window_hours)
    download_bars, download_values = _daily_volume_bars(days=upload_window_days, daily_key="download_daily")

    system_cards = [
        {
            "label": "CPU Usage",
            "value": _format_percent(cpu_percent),
            "detail": (quicklook or {}).get("cpu_name", "Raspberry Pi") if isinstance(quicklook, dict) else "Raspberry Pi",
        },
        {
            "label": "CPU Temp",
            "value": _format_temperature(cpu_temp_c),
            "detail": f"{trend_window_hours}h avg {_format_temperature(_mean(temp_values))}",
        },
        {
            "label": "Memory",
            "value": _format_percent(memory_percent),
            "detail": _format_bytes((mem or {}).get("available") if isinstance(mem, dict) else None),
        },
        {
            "label": "Host Uptime",
            "value": host_uptime,
            "detail": f"load {load_detail}",
        },
        {
            "label": "Services",
            "value": f"{running_services}/{total_services}",
            "detail": "running containers",
        },
        {
            "label": "Anime Data",
            "value": _format_percent(disk.get("percent")),
            "detail": _format_bytes(disk.get("free_bytes")),
        },
    ]

    queue_cards = [
        {
            "label": "Bangumi Tasks",
            "value": str((qb or {}).get("task_count", "-")) if qb else "-",
            "detail": (qb or {}).get("category", "Bangumi") if qb else "qB unavailable",
        },
        {
            "label": "Downloading",
            "value": str((qb or {}).get("active_downloads", "-")) if qb else "-",
            "detail": _format_rate((qb or {}).get("download_speed") if qb else None),
        },
        {
            "label": "Seeding",
            "value": str((qb or {}).get("active_seeds", "-")) if qb else "-",
            "detail": _format_rate((qb or {}).get("upload_speed") if qb else None),
        },
        {
            "label": "Seasonal Episodes",
            "value": str(_count_media_files(seasonal_root)),
            "detail": f"{_count_series_dirs(seasonal_root)} 部作品",
        },
        {
            "label": "Manual Review",
            "value": str(_count_media_files(manual_review_root)),
            "detail": "待人工处理文件",
        },
        {
            "label": "Download Residue",
            "value": str(_count_media_files(downloads_root)),
            "detail": "下载区剩余媒体文件",
        },
    ]
    manual_review_count = _count_media_files(manual_review_root)
    log_count = len(read_events())

    network_cards = [
        {
            "label": "Tailnet",
            "value": (tailscale or {}).get("BackendState", "unknown") if tailscale else "unavailable",
            "detail": tailscale_self.get("HostName") or base_host,
        },
        {
            "label": "Tailscale IP",
            "value": _tailscale_ip_pair(tailscale_self.get("TailscaleIPs") if tailscale_self else None)[0],
            "detail": _strip_trailing_dot(tailscale_self.get("DNSName")) if tailscale_self else "-",
        },
        {
            "label": "Peers",
            "value": str(len(tailscale_peer_values)) if tailscale else "-",
            "detail": f"{tailnet_online_peers} online" if tailscale else "local api unavailable",
        },
    ]

    trend_cards = [
        {
            "label": "CPU Usage",
            "value": _format_percent(cpu_percent),
            "detail": f"{trend_window_hours}h · load {load_detail}",
            "points": cpu_points,
            "chart_kind": "line",
            "window_label": f"{trend_window_hours}H",
            "tone": "teal",
        },
        {
            "label": "CPU Temp",
            "value": _format_temperature(cpu_temp_c),
            "detail": f"{trend_window_hours}h avg {_format_temperature(_mean(temp_values))}",
            "points": temp_points,
            "chart_kind": "line",
            "window_label": f"{trend_window_hours}H",
            "tone": "amber",
        },
        {
            "label": "Playback Traffic",
            "value": _format_rate(playback_tx_rate),
            "detail": f"{trend_window_hours}h avg {_format_rate(_mean(playback_values))} · all clients",
            "points": playback_points,
            "chart_kind": "line",
            "window_label": f"{trend_window_hours}H",
            "tone": "ocean",
        },
        {
            "label": "Download Volume",
            "value": _format_bytes(sum(download_values)),
            "detail": f"{upload_window_days}d total · qBittorrent",
            "bars": download_bars,
            "chart_kind": "bars",
            "window_label": f"{upload_window_days}D",
            "tone": "violet",
        },
    ]

    diagnostics = []
    for label, error in (
        ("glances/quicklook", quicklook_error),
        ("glances/containers", containers_error),
        ("glances/mem", mem_error),
        ("glances/uptime", uptime_error),
        ("glances/load", load_error),
        ("glances/sensors", sensors_error),
        ("qBittorrent", qb_error),
        ("tailscale", tailscale_error),
    ):
        if error:
            diagnostics.append({"source": label, "message": error})

    return {
        "title": "RPI Anime Ops",
        "subtitle": "树莓派私人影音库控制台",
        "host": base_host,
        "refresh_interval_seconds": _refresh_interval_seconds(),
        "services": _build_services(
            base_host,
            containers,
            tailscale,
            manual_review_count=manual_review_count,
            log_count=log_count,
        ),
        "system_cards": system_cards,
        "queue_cards": queue_cards,
        "trend_cards": trend_cards,
        "network_cards": network_cards,
        "generated_from": {
            "glances": glances_base,
            "tailscale_socket": tailscale_socket,
            "history_file": str(_history_file()),
        },
        "diagnostics": diagnostics,
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


app = FastAPI(title="Anime Ops UI", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/overview")
def overview() -> JSONResponse:
    return JSONResponse(build_overview())


@app.get("/api/manual-review")
def manual_review() -> JSONResponse:
    return JSONResponse(build_manual_review_payload())


@app.get("/api/manual-review/item")
def manual_review_item(id: str = Query(...)) -> JSONResponse:
    return JSONResponse(build_manual_review_item_payload(id))


@app.get("/api/logs")
def logs_api(
    level: str | None = Query(default=None),
    source: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=300, ge=20, le=1500),
) -> JSONResponse:
    return JSONResponse(
        build_logs_payload(
            level=level,
            source=source,
            search=q,
            limit=limit,
        )
    )


@app.get("/api/tailscale")
def tailscale_api() -> JSONResponse:
    return JSONResponse(build_tailscale_payload())


@app.get("/api/postprocessor")
def postprocessor_api() -> JSONResponse:
    return JSONResponse(build_postprocessor_payload())


@app.post("/api/tailscale/action")
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


@app.post("/api/logs/clear")
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


@app.post("/api/manual-review/item/retry-parse")
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


@app.post("/api/manual-review/item/publish")
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


@app.post("/api/manual-review/item/delete")
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


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/ops-review")
def ops_review_placeholder() -> FileResponse:
    return FileResponse(STATIC_DIR / "ops-review.html")


@app.get("/ops-review/item")
def ops_review_item_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "ops-review-item.html")


@app.get("/postprocessor")
def postprocessor_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "postprocessor.html")


@app.get("/tailscale")
def tailscale_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "tailscale.html")


@app.get("/logs")
def logs_placeholder() -> FileResponse:
    return FileResponse(STATIC_DIR / "logs.html")


def main() -> None:
    import uvicorn

    uvicorn.run("anime_ops_ui.main:app", host="0.0.0.0", port=3000, reload=False)


if __name__ == "__main__":
    main()
