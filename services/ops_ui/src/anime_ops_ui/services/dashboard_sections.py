from __future__ import annotations

from typing import Any


def build_hero_section(
    *,
    host: str,
    service_summary: dict[str, Any],
    tailscaled_online: bool,
    tailnet_online_peers: int,
    data_storage_ready: bool,
) -> dict[str, Any]:
    return {
        "title": "Operations Dashboard",
        "subtitle": "Data-dense control surface for the anime stack",
        "host": host,
        "service_status": service_summary.get("value", "-"),
        "tailnet_status": "online" if tailscaled_online else "offline",
        "tailnet_online_peers": tailnet_online_peers,
        "storage_status": "ready" if data_storage_ready else "degraded",
    }


def build_summary_strip(
    *,
    service_summary: dict[str, Any],
    queue_cards: list[dict[str, Any]],
    manual_review_count: int | None,
    diagnostics: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    task_card = queue_cards[0] if queue_cards else {"label": "Bangumi Tasks", "value": "-", "detail": "-"}
    downloading_card = queue_cards[1] if len(queue_cards) > 1 else {"label": "Downloading", "value": "-", "detail": "-"}
    return [
        {
            "id": "services",
            "label": service_summary.get("label", "Services"),
            "value": service_summary.get("value", "-"),
            "detail": service_summary.get("detail", "-"),
        },
        {
            "id": "tasks",
            "label": task_card.get("label", "Bangumi Tasks"),
            "value": task_card.get("value", "-"),
            "detail": task_card.get("detail", "-"),
        },
        {
            "id": "downloading",
            "label": downloading_card.get("label", "Downloading"),
            "value": downloading_card.get("value", "-"),
            "detail": downloading_card.get("detail", "-"),
        },
        {
            "id": "manual_review",
            "label": "Manual Review",
            "value": str(manual_review_count) if manual_review_count is not None else "-",
            "detail": "待人工处理文件" if manual_review_count is not None else "数据盘未挂载",
        },
        {
            "id": "diagnostics",
            "label": "Diagnostics",
            "value": str(len(diagnostics)),
            "detail": "active warnings",
        },
    ]


def build_service_rows(*, services: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for service in services:
        status = str(service.get("status", "unknown"))
        rows.append(
            {
                "id": service.get("id"),
                "name": service.get("name"),
                "status": status,
                "status_tone": _status_tone(status),
                "href": service.get("href"),
                "meta": service.get("meta"),
                "uptime": service.get("uptime"),
                "description": service.get("description"),
                "internal": bool(service.get("internal", False)),
                "restart_target": service.get("restart_target"),
                "restart_label": service.get("restart_label"),
                "restart_requires_reload": bool(service.get("restart_requires_reload", False)),
                "restart_name": service.get("restart_name"),
            }
        )
    return rows


def _status_tone(status: str) -> str:
    normalized = status.strip().lower()
    if normalized in {"running", "online", "healthy"}:
        return "success"
    if normalized in {"offline", "exited", "dead", "failed"}:
        return "danger"
    return "neutral"
