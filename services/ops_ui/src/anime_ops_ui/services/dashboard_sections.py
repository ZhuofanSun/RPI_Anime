from __future__ import annotations

from typing import Any


def build_dashboard_hero(
    *,
    title: str,
    active_downloads: int,
    review_count: int,
    diagnostics: list[dict[str, Any]],
    tailnet_online: bool,
    host: str | None = None,
) -> dict[str, Any]:
    blocking_count = len([item for item in diagnostics if item.get("source") != "fan-control"])
    status_tone = "teal" if blocking_count == 0 else "rose"
    status_label = "Stable" if blocking_count == 0 else f"{blocking_count} 个风险待处理"
    return {
        "eyebrow": "Control Surface",
        "title": title,
        "summary": f"{active_downloads} 个下载中 · {review_count} 个待审核 · {'Tailnet 在线' if tailnet_online else 'Tailnet 异常'}",
        "status_tone": status_tone,
        "status_label": status_label,
        "host": host,
    }


def build_summary_strip(
    *,
    active_downloads: int,
    review_count: int,
    diagnostics: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "question": "今天有什么值得看",
            "answer": f"{active_downloads} 个下载中",
            "tone": "teal",
        },
        {
            "question": "下载和入库链路是否正常",
            "answer": f"{review_count} 个待审核",
            "tone": "amber" if review_count else "teal",
        },
        {
            "question": "设备和远程访问是否健康",
            "answer": "有异常" if diagnostics else "运行稳定",
            "tone": "rose" if diagnostics else "teal",
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
                "meta": service.get("meta"),
                "uptime": service.get("uptime"),
                "href": service.get("href"),
                "internal": bool(service.get("internal", False)),
                "restart_target": service.get("restart_target"),
                "restart_label": service.get("restart_label"),
                "restart_requires_reload": bool(service.get("restart_requires_reload", False)),
                "restart_name": service.get("restart_name"),
            }
        )
    return rows
