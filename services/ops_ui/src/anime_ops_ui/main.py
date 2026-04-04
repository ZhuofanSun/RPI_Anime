from __future__ import annotations

import http.client
import json
import os
import shutil
import socket
from pathlib import Path
from typing import Any

import requests
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
MEDIA_EXTENSIONS = {".mkv", ".mp4", ".avi", ".m4v", ".ts"}


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


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


def _glances_base_url() -> str:
    return _env("GLANCES_API_URL", "http://glances:61208/api/4").rstrip("/")


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

        transfer = session.get(
            f"{base_url}/api/v2/transfer/info",
            timeout=5,
        )
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
        }, None
    except Exception as exc:  # pragma: no cover - defensive wrapper
        return None, str(exc)


def _build_services(base_host: str, containers: dict[str, dict[str, Any]], tailscale: dict[str, Any] | None) -> list[dict[str, Any]]:
    tailscale_self = (tailscale or {}).get("Self", {})
    tailscale_state = "online" if (tailscale or {}).get("BackendState") == "Running" else "offline"
    return [
        {
            "name": "Jellyfin",
            "href": _service_link(base_host, int(_env("JELLYFIN_PORT", "8096"))),
            "description": "私人影音库与播放入口",
            "status": containers.get("jellyfin", {}).get("status", "unknown"),
            "meta": "Media server",
        },
        {
            "name": "qBittorrent",
            "href": _service_link(base_host, int(_env("QBITTORRENT_WEBUI_PORT", "8080"))),
            "description": "下载、任务队列和分类",
            "status": containers.get("qbittorrent", {}).get("status", "unknown"),
            "meta": "Download client",
        },
        {
            "name": "AutoBangumi",
            "href": _service_link(base_host, int(_env("AUTOBANGUMI_PORT", "7892"))),
            "description": "RSS 订阅、规则和自动投递",
            "status": containers.get("autobangumi", {}).get("status", "unknown"),
            "meta": "Subscription",
        },
        {
            "name": "Glances",
            "href": _service_link(base_host, int(_env("GLANCES_PORT", "61208"))),
            "description": "更细的系统、容器和进程监控页",
            "status": containers.get("glances", {}).get("status", "unknown"),
            "meta": "System monitor",
        },
        {
            "name": "Postprocessor",
            "href": None,
            "description": "下载完成后的选优、发布和 NFO 生成",
            "status": containers.get("anime-postprocessor", {}).get("status", "unknown"),
            "meta": "Background worker",
        },
        {
            "name": "Manual Review",
            "href": None,
            "description": "人工审核页将在下一阶段接入这里",
            "status": "coming-soon",
            "meta": "Queued next",
        },
        {
            "name": "Tailscale",
            "href": None,
            "description": "本地 tailnet 状态与远程访问链路",
            "status": tailscale_state,
            "meta": tailscale_self.get("TailscaleIPs", ["-"])[0] if tailscale_self else "-",
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
    anime_data_root = Path(_env("ANIME_DATA_ROOT", "/srv/anime-data"))
    base_host = _env("HOMEPAGE_BASE_HOST", socket.gethostname())
    glances_base = _glances_base_url()
    disk = _disk_snapshot(anime_data_root)

    quicklook, quicklook_error = _safe_get_json(f"{glances_base}/quicklook")
    containers_raw, containers_error = _safe_get_json(f"{glances_base}/containers")
    mem, mem_error = _safe_get_json(f"{glances_base}/mem")
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

    system_cards = [
        {
            "label": "CPU",
            "value": _format_percent((quicklook or {}).get("cpu") if isinstance(quicklook, dict) else None),
            "detail": (quicklook or {}).get("cpu_name", "Raspberry Pi") if isinstance(quicklook, dict) else "Raspberry Pi",
        },
        {
            "label": "Memory",
            "value": _format_percent((mem or {}).get("percent") if isinstance(mem, dict) else None),
            "detail": _format_bytes((mem or {}).get("available") if isinstance(mem, dict) else None),
        },
        {
            "label": "Anime Data",
            "value": _format_percent(disk.get("percent")),
            "detail": _format_bytes(disk.get("free_bytes")),
        },
        {
            "label": "Manual Review",
            "value": str(_count_media_files(manual_review_root)),
            "detail": "待人工处理文件",
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
        {
            "label": "Download Residue",
            "value": str(_count_media_files(downloads_root)),
            "detail": "下载区剩余媒体文件",
        },
    ]

    diagnostics = []
    for label, error in (
        ("glances/quicklook", quicklook_error),
        ("glances/containers", containers_error),
        ("glances/mem", mem_error),
        ("qBittorrent", qb_error),
        ("tailscale", tailscale_error),
    ):
        if error:
            diagnostics.append({"source": label, "message": error})

    return {
        "title": "RPI Anime Ops",
        "subtitle": "树莓派私人影音库控制台",
        "host": base_host,
        "services": _build_services(base_host, containers, tailscale),
        "system_cards": system_cards,
        "queue_cards": queue_cards,
        "network_cards": network_cards,
        "generated_from": {
            "glances": glances_base,
            "tailscale_socket": tailscale_socket,
        },
        "diagnostics": diagnostics,
    }


app = FastAPI(title="Anime Ops UI")
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


def main() -> None:
    import uvicorn

    uvicorn.run("anime_ops_ui.main:app", host="0.0.0.0", port=3000, reload=False)


if __name__ == "__main__":
    main()
