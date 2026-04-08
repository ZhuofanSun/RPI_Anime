from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


def _review_item_from_path(path: Path, review_root: Path) -> dict[str, Any]:
    from anime_ops_ui import main as main_module

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
        "reason": main_module._review_bucket_reason(bucket),
        "relative_path": str(relative),
        "filename": path.name,
        "stem": path.stem,
        "extension": path.suffix.lower() or "-",
        "series_name": series_name,
        "season_label": season_label or "-",
        "folder_hint": folder_hint,
        "size_bytes": stat.st_size,
        "size_label": main_module._format_bytes(stat.st_size),
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "modified_label": main_module._format_timestamp(stat.st_mtime),
    }


def _manual_review_items(review_root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not review_root.exists():
        return items
    for path in sorted(review_root.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".mkv", ".mp4", ".avi", ".m4v", ".ts"}:
            items.append(_review_item_from_path(path, review_root))
    items.sort(key=lambda item: item["modified_at"], reverse=True)
    return items


def _review_siblings(item_path: Path, review_root: Path) -> list[dict[str, Any]]:
    from anime_ops_ui import main as main_module

    siblings = []
    for path in sorted(item_path.parent.iterdir()):
        if not path.is_file() or path.suffix.lower() not in main_module.MEDIA_EXTENSIONS:
            continue
        sibling = _review_item_from_path(path, review_root)
        sibling["is_current"] = path == item_path
        siblings.append(sibling)
    return siblings


def build_manual_review_payload() -> dict[str, Any]:
    from anime_ops_ui import main as main_module

    review_root = main_module._manual_review_root()
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
            "size_label": main_module._format_bytes(stats["size_bytes"]),
        }
        for bucket, stats in sorted(bucket_stats.items(), key=lambda entry: (-entry[1]["count"], entry[0]))
    ]

    summary_cards = [
        {
            "label": "Review Files",
            "value": str(len(items)),
            "detail": "待处理媒体文件",
        },
        {
            "label": "Total Size",
            "value": main_module._format_bytes(total_bytes),
            "detail": str(review_root),
        },
        {
            "label": "Series",
            "value": str(len(series_names)),
            "detail": "不同作品目录",
        },
        {
            "label": "Buckets",
            "value": str(len(buckets)),
            "detail": ", ".join(bucket["label"] for bucket in buckets[:3]) if buckets else "当前没有分组",
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
        "total_size_label": main_module._format_bytes(total_bytes),
        "last_updated": datetime.now().isoformat(timespec="seconds"),
    }


def build_manual_review_item_payload(item_id: str) -> dict[str, Any]:
    from anime_ops_ui import main as main_module

    review_root = main_module._manual_review_root()
    items = _manual_review_items(review_root)
    item = next((entry for entry in items if entry["id"] == item_id), None)
    if item is None:
        raise KeyError(item_id)
    item_path = review_root / item["relative_path"]
    auto_parse = main_module._build_auto_parse_payload(item_path, review_root)
    manual_publish_defaults = main_module._manual_publish_defaults(item, auto_parse)
    return {
        "title": "Review Detail",
        "subtitle": item["filename"],
        "refresh_interval_seconds": 15,
        "item": item,
        "root": str(review_root),
        "path": str(item_path),
        "content_type": "media",
        "auto_parse": auto_parse,
        "manual_publish_defaults": manual_publish_defaults,
        "siblings": _review_siblings(item_path, review_root),
        "breadcrumbs": [
            {"label": "Dashboard", "href": "/"},
            {"label": "Ops Review", "href": "/ops-review"},
            {"label": item["filename"]},
        ],
        "last_updated": datetime.now().isoformat(timespec="seconds"),
    }


def list_manual_review_items() -> dict[str, Any]:
    return build_manual_review_payload()


def get_manual_review_item(item_id: str) -> dict[str, Any]:
    return build_manual_review_item_payload(item_id)
