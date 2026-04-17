from __future__ import annotations

import json
from typing import Any

from anime_ops_ui import runtime_main_module
from anime_ops_ui.copy import payload_copy


def build_logs_payload(
    *,
    level: str | None = None,
    source: str | None = None,
    search: str | None = None,
    limit: int = 300,
    locale: str | None = None,
) -> dict[str, Any]:
    main_module = runtime_main_module()

    copy = payload_copy("logs", locale)
    summary_copy = copy["summary_cards"]
    raw_events = main_module.read_events()
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

    visible = filtered[: max(20, min(limit, main_module.event_log_cap()))]
    levels = sorted({str(item.get("level", "info")) for item in raw_events})
    sources = sorted({str(item.get("source", "unknown")) for item in raw_events})
    level_counts: dict[str, int] = {}
    for item in raw_events:
        item_level = str(item.get("level", "info"))
        level_counts[item_level] = level_counts.get(item_level, 0) + 1

    summary_cards = [
        {
            "label": summary_copy["visible"]["label"],
            "value": str(len(visible)),
            "detail": summary_copy["visible"]["detail"].format(matched=len(filtered), total=len(raw_events)),
        },
        {
            "label": summary_copy["sources"]["label"],
            "value": str(len(sources)),
            "detail": ", ".join(sources[:3]) if sources else summary_copy["sources"]["empty"],
        },
        {
            "label": summary_copy["errors"]["label"],
            "value": str(level_counts.get("error", 0)),
            "detail": summary_copy["errors"]["detail"].format(warnings=level_counts.get("warning", 0)),
        },
        {
            "label": summary_copy["retention"]["label"],
            "value": str(main_module.event_log_cap()),
            "detail": str(main_module.event_log_path()),
        },
    ]

    return {
        "title": copy["title"],
        "subtitle": copy["subtitle"],
        "copy": copy["page"],
        "refresh_interval_seconds": 10,
        "summary_cards": summary_cards,
        "levels": levels,
        "sources": sources,
        "items": visible,
        "total_count": len(raw_events),
        "matched_count": len(filtered),
        "retention_cap": main_module.event_log_cap(),
        "storage_path": str(main_module.event_log_path()),
        "last_updated": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
    }


def list_log_events(
    *,
    source: str | None = None,
    level: str | None = None,
    search: str | None = None,
    limit: int = 300,
    locale: str | None = None,
) -> dict[str, Any]:
    return build_logs_payload(source=source, level=level, search=search, limit=limit, locale=locale)
