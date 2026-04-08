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

SERVICE_ACTIONS = [
    {"id": "jellyfin", "label": "Restart Jellyfin", "name": "Jellyfin", "target": "jellyfin", "icon": "J", "requires_reload": False},
    {"id": "qbittorrent", "label": "Restart qBittorrent", "name": "qBittorrent", "target": "qbittorrent", "icon": "Q", "requires_reload": False},
    {"id": "autobangumi", "label": "Restart AutoBangumi", "name": "AutoBangumi", "target": "autobangumi", "icon": "A", "requires_reload": False},
    {"id": "glances", "label": "Restart Glances", "name": "Glances", "target": "glances", "icon": "G", "requires_reload": False},
    {"id": "postprocessor", "label": "Restart Postprocessor", "name": "Postprocessor", "target": "postprocessor", "icon": "P", "requires_reload": False},
    {"id": "homepage", "label": "Restart Ops UI", "name": "Ops UI", "target": "homepage", "icon": "OR", "requires_reload": True},
    {"id": "tailscale", "label": "Restart Tailscale", "name": "Tailscale", "target": "tailscale", "icon": "T", "requires_reload": False},
]

STACK_ACTION = {
    "label": "Service Actions",
    "hint": "single + stack restart",
    "stack_label": "Restart Stack",
    "stack_detail": "compose only · homepage last",
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
