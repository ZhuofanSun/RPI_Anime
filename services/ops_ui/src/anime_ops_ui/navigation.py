from __future__ import annotations

import copy
import os
import socket

INTERNAL_PAGES = {
    "dashboard": {"label": "Dashboard", "path": "/", "icon": "D", "target": "internal"},
    "ops-review": {"label": "Ops Review", "path": "/ops-review", "icon": "OR", "target": "internal"},
    "logs": {"label": "Logs", "path": "/logs", "icon": "L", "target": "internal"},
    "postprocessor": {"label": "Postprocessor", "path": "/postprocessor", "icon": "P", "target": "internal"},
    "tailscale": {"label": "Tailscale", "path": "/tailscale", "icon": "T", "target": "internal"},
}

EXTERNAL_SERVICES = {
    "jellyfin": {"label": "Jellyfin", "icon": "J", "target": "external", "port_env": "JELLYFIN_PORT", "default_port": 8096},
    "qbittorrent": {"label": "qBittorrent", "icon": "Q", "target": "external", "port_env": "QBITTORRENT_WEBUI_PORT", "default_port": 8080},
    "autobangumi": {"label": "AutoBangumi", "icon": "A", "target": "external", "port_env": "AUTOBANGUMI_PORT", "default_port": 7892},
    "glances": {"label": "Glances", "icon": "G", "target": "external", "port_env": "GLANCES_PORT", "default_port": 61208},
}


def _safe_port(raw: str, fallback: int) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return fallback


def service_link(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def build_external_services_with_hrefs() -> dict[str, dict]:
    base_host = os.environ.get("HOMEPAGE_BASE_HOST", socket.gethostname())
    services = copy.deepcopy(EXTERNAL_SERVICES)
    for _, item in services.items():
        fallback_port = int(item.get("default_port", 80))
        port = _safe_port(os.environ.get(item["port_env"], str(fallback_port)), fallback_port)
        item["href"] = service_link(base_host, port)
    return services
