from __future__ import annotations

import copy
import os
import socket

from anime_ops_ui.i18n import DEFAULT_LOCALE, normalize_locale

_INTERNAL_PAGE_DEFS = {
    "dashboard": {"path": "/", "icon": "D", "target": "internal"},
    "ops-review": {"path": "/ops-review", "icon": "OR", "target": "internal"},
    "logs": {"path": "/logs", "icon": "L", "target": "internal"},
    "postprocessor": {"path": "/postprocessor", "icon": "P", "target": "internal"},
    "tailscale": {"path": "/tailscale", "icon": "T", "target": "internal"},
}

_INTERNAL_PAGE_LABELS = {
    "zh-Hans": {
        "dashboard": "总览",
        "ops-review": "审核队列",
        "logs": "日志",
        "postprocessor": "后处理",
        "tailscale": "Tailscale",
    },
    "en": {
        "dashboard": "Dashboard",
        "ops-review": "Ops Review",
        "logs": "Logs",
        "postprocessor": "Postprocessor",
        "tailscale": "Tailscale",
    },
}

_EXTERNAL_SERVICE_DEFS = {
    "jellyfin": {"label": "Jellyfin", "icon": "J", "target": "external", "port_env": "JELLYFIN_PORT", "default_port": 8096},
    "qbittorrent": {"label": "qBittorrent", "icon": "Q", "target": "external", "port_env": "QBITTORRENT_WEBUI_PORT", "default_port": 8080},
    "autobangumi": {"label": "AutoBangumi", "icon": "A", "target": "external", "port_env": "AUTOBANGUMI_PORT", "default_port": 7892},
    "glances": {"label": "Glances", "icon": "G", "target": "external", "port_env": "GLANCES_PORT", "default_port": 61208},
}

_SERVICE_ACTION_DEFS = [
    {"id": "jellyfin", "name": "Jellyfin", "target": "jellyfin", "icon": "J", "requires_reload": False},
    {"id": "qbittorrent", "name": "qBittorrent", "target": "qbittorrent", "icon": "Q", "requires_reload": False},
    {"id": "autobangumi", "name": "AutoBangumi", "target": "autobangumi", "icon": "A", "requires_reload": False},
    {"id": "glances", "name": "Glances", "target": "glances", "icon": "G", "requires_reload": False},
    {"id": "postprocessor", "name": "Postprocessor", "target": "postprocessor", "icon": "P", "requires_reload": False},
    {"id": "homepage", "name": "Ops UI", "target": "homepage", "icon": "OR", "requires_reload": True},
    {"id": "tailscale", "name": "Tailscale", "target": "tailscale", "icon": "T", "requires_reload": False},
]

_STACK_ACTION_COPY = {
    "zh-Hans": {
        "label": "服务动作",
        "hint": "单服务 + 整栈重启",
        "stack_label": "重启服务栈",
        "stack_detail": "仅 compose · 最后重启 Ops UI",
    },
    "en": {
        "label": "Service Actions",
        "hint": "single + stack restart",
        "stack_label": "Restart Stack",
        "stack_detail": "compose only · homepage last",
    },
}


def build_internal_pages(locale: str | None = None) -> dict[str, dict]:
    normalized_locale = normalize_locale(locale or DEFAULT_LOCALE)
    labels = _INTERNAL_PAGE_LABELS[normalized_locale]
    return {
        page_id: {
            **item,
            "label": labels[page_id],
        }
        for page_id, item in _INTERNAL_PAGE_DEFS.items()
    }


def build_external_services(locale: str | None = None) -> dict[str, dict]:
    _ = normalize_locale(locale or DEFAULT_LOCALE)
    return copy.deepcopy(_EXTERNAL_SERVICE_DEFS)


def build_service_actions(locale: str | None = None) -> list[dict]:
    normalized_locale = normalize_locale(locale or DEFAULT_LOCALE)
    restart_verb = "重启" if normalized_locale == "zh-Hans" else "Restart"
    return [
        {
            **item,
            "label": f"{restart_verb} {item['name']}",
        }
        for item in copy.deepcopy(_SERVICE_ACTION_DEFS)
    ]


def build_stack_action(locale: str | None = None) -> dict:
    normalized_locale = normalize_locale(locale or DEFAULT_LOCALE)
    return copy.deepcopy(_STACK_ACTION_COPY[normalized_locale])


INTERNAL_PAGES = build_internal_pages(DEFAULT_LOCALE)
EXTERNAL_SERVICES = build_external_services(DEFAULT_LOCALE)
SERVICE_ACTIONS = build_service_actions(DEFAULT_LOCALE)
STACK_ACTION = build_stack_action(DEFAULT_LOCALE)


def _safe_port(raw: str, fallback: int) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return fallback


def service_link(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def build_external_services_with_hrefs(locale: str | None = None) -> dict[str, dict]:
    base_host = os.environ.get("HOMEPAGE_BASE_HOST", socket.gethostname())
    services = build_external_services(locale)
    for _, item in services.items():
        fallback_port = int(item.get("default_port", 80))
        port = _safe_port(os.environ.get(item["port_env"], str(fallback_port)), fallback_port)
        item["href"] = service_link(base_host, port)
    return services
