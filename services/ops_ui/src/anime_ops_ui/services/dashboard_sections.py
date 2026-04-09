from __future__ import annotations

from typing import Any

from anime_ops_ui.copy import payload_copy


def build_dashboard_hero(
    *,
    title: str,
    active_downloads: int,
    review_count: int,
    diagnostics: list[dict[str, Any]],
    tailnet_online: bool,
    host: str | None = None,
    locale: str | None = None,
) -> dict[str, Any]:
    copy = payload_copy("overview", locale)["hero"]
    blocking_count = len([item for item in diagnostics if item.get("source") != "fan-control"])
    status_tone = "teal" if blocking_count == 0 else "rose"
    status_label = copy["status_stable"] if blocking_count == 0 else copy["status_risks"].format(count=blocking_count)
    return {
        "eyebrow": copy["eyebrow"],
        "title": title,
        "summary": copy["summary"].format(
            downloads=active_downloads,
            reviews=review_count,
            tailnet=copy["tailnet_online"] if tailnet_online else copy["tailnet_issue"],
        ),
        "status_tone": status_tone,
        "status_label": status_label,
        "host": host,
    }


def build_summary_strip(
    *,
    active_downloads: int,
    review_count: int,
    diagnostics: list[dict[str, Any]],
    locale: str | None = None,
) -> list[dict[str, Any]]:
    copy = payload_copy("overview", locale)["summary_strip"]
    return [
        {
            "question": copy["watch_question"],
            "answer": copy["watch_answer"].format(count=active_downloads),
            "tone": "teal",
        },
        {
            "question": copy["ingest_question"],
            "answer": copy["ingest_answer"].format(count=review_count),
            "tone": "amber" if review_count else "teal",
        },
        {
            "question": copy["health_question"],
            "answer": copy["health_issue"] if diagnostics else copy["health_ok"],
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
