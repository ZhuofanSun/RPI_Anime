from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
import http.client
import json
import os
import shutil
import socket
from pathlib import Path
import threading
import time
from typing import Any

import requests
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
MEDIA_EXTENSIONS = {".mkv", ".mp4", ".avi", ".m4v", ".ts"}
HISTORY_LOCK = threading.Lock()
HISTORY_SERIES = ("cpu_percent", "cpu_temp_c", "playback_tx_rate")
HISTORY_STATE: dict[str, Any] | None = None


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


def _tailscale_status(socket_path: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        class UnixHTTPConnection(http.client.HTTPConnection):
            def __init__(self, unix_socket_path: str, timeout: int) -> None:
                super().__init__("local-tailscaled.sock", timeout=timeout)
                self.unix_socket_path = unix_socket_path

            def connect(self) -> None:
                self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.sock.settimeout(self.timeout)
                self.sock.connect(self.unix_socket_path)

        connection = UnixHTTPConnection(socket_path, timeout=5)
        connection.request(
            "GET",
            "/localapi/v0/status",
            headers={"Host": "local-tailscaled.sock", "Sec-Tailscale": "localapi"},
        )
        response = connection.getresponse()
        body = response.read()
        connection.close()
        if response.status != 200:
            raise RuntimeError(f"{response.status} {response.reason}")
        return json.loads(body.decode("utf-8")), None
    except Exception as exc:  # pragma: no cover - defensive wrapper
        return None, str(exc)


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


def _build_services(base_host: str, containers: dict[str, dict[str, Any]], tailscale: dict[str, Any] | None) -> list[dict[str, Any]]:
    tailscale_self = (tailscale or {}).get("Self", {})
    tailscale_state = "online" if (tailscale or {}).get("BackendState") == "Running" else "offline"
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
            "href": None,
            "description": "下载完成后的选优、发布和 NFO 生成",
            "status": containers.get("anime-postprocessor", {}).get("status", "unknown"),
            "meta": "Background worker",
            "uptime": container_uptime("anime-postprocessor"),
        },
        {
            "name": "Ops Review",
            "href": f"{ops_ui_base}/ops-review",
            "description": "人工审核页占位，下一阶段会从这里接入",
            "status": "coming-soon",
            "meta": "Preview route",
            "uptime": "Next phase",
        },
        {
            "name": "Logs",
            "href": f"{ops_ui_base}/logs",
            "description": "完整日志页占位，下一阶段会聚合服务日志",
            "status": "coming-soon",
            "meta": "Logs route",
            "uptime": "Next phase",
        },
        {
            "name": "Tailscale",
            "href": None,
            "description": "本地 tailnet 状态与远程访问链路",
            "status": tailscale_state,
            "meta": tailscale_self.get("TailscaleIPs", ["-"])[0] if tailscale_self else "-",
            "uptime": tailscale_self.get("DNSName", "-").rstrip(".") if tailscale_self else None,
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

    tailscale_self = (tailscale or {}).get("Self", {})
    tailscale_peers = (tailscale or {}).get("Peer", {}) if isinstance(tailscale, dict) else {}
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

    network_cards = [
        {
            "label": "Tailnet",
            "value": (tailscale or {}).get("BackendState", "unknown") if tailscale else "unavailable",
            "detail": tailscale_self.get("HostName", base_host),
        },
        {
            "label": "Tailscale IP",
            "value": tailscale_self.get("TailscaleIPs", ["-"])[0] if tailscale_self else "-",
            "detail": tailscale_self.get("DNSName", "-").rstrip(".") if tailscale_self else "-",
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
        "services": _build_services(base_host, containers, tailscale),
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


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/ops-review")
def ops_review_placeholder() -> FileResponse:
    return FileResponse(STATIC_DIR / "ops-review.html")


@app.get("/logs")
def logs_placeholder() -> FileResponse:
    return FileResponse(STATIC_DIR / "logs.html")


def main() -> None:
    import uvicorn

    uvicorn.run("anime_ops_ui.main:app", host="0.0.0.0", port=3000, reload=False)


if __name__ == "__main__":
    main()
