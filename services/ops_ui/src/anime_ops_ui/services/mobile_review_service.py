from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from anime_ops_ui import runtime_main_module
from anime_ops_ui.copy import review_auto_parse_reason
from anime_ops_ui.i18n import normalize_locale
from anime_ops_ui.services.review_service import get_manual_review_item, list_manual_review_items


def _locale_text(locale: str | None, *, en: str, zh: str) -> str:
    return en if normalize_locale(locale) == "en" else zh


def _review_title(item: dict[str, Any], defaults: dict[str, Any] | None = None) -> str:
    default_title = (defaults or {}).get("title")
    return str(
        default_title
        or item.get("series_name")
        or item.get("stem")
        or item.get("filename")
        or "Review Item"
    )


def _episode_label(episode: int | None, *, locale: str | None = None) -> str | None:
    if episode is None:
        return None
    return _locale_text(locale, en=f"Episode {episode}", zh=f"第 {episode} 集")


def _queue_episode_hint(item: dict[str, Any]) -> int | None:
    main_module = runtime_main_module()
    try:
        return int(main_module._guess_episode_number(str(item.get("filename") or "")) or 0) or None
    except (TypeError, ValueError):
        return None


def _queue_summary(item: dict[str, Any], *, locale: str | None = None) -> str:
    parts: list[str] = []
    episode_hint = _queue_episode_hint(item)
    if episode_hint is not None:
        parts.append(_episode_label(episode_hint, locale=locale) or "")
    elif str(item.get("season_label") or "-") != "-":
        parts.append(str(item["season_label"]))
    filename = str(item.get("filename") or "").strip()
    if filename:
        parts.append(filename)
    return " · ".join(part for part in parts if part)


def _detail_payload_or_404(review_item_id: str, *, locale: str | None = None) -> dict[str, Any]:
    try:
        return get_manual_review_item(review_item_id, locale=locale)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="manual review file not found") from exc


def build_review_queue_payload(*, locale: str | None = None) -> dict[str, Any]:
    payload = list_manual_review_items(locale=locale)
    items = [
        {
            "reviewItemId": item["id"],
            "title": _review_title(item),
            "summary": _queue_summary(item, locale=locale),
            "failureReason": item["reason"],
            "state": "pending",
            "queuedAt": item["modified_at"],
        }
        for item in payload.get("items", [])
        if isinstance(item, dict)
    ]
    return {
        "items": items,
        "updatedAt": payload.get("last_updated"),
    }


def build_review_detail_payload(review_item_id: str, *, locale: str | None = None) -> dict[str, Any]:
    payload = _detail_payload_or_404(review_item_id, locale=locale)
    item = payload["item"]
    auto_parse = payload.get("auto_parse") if isinstance(payload.get("auto_parse"), dict) else {}
    defaults = payload.get("manual_publish_defaults") if isinstance(payload.get("manual_publish_defaults"), dict) else {}
    episode_hint = _episode_label(defaults.get("episode"), locale=locale)
    detail = {
        "reviewItemId": item["id"],
        "title": _review_title(item, defaults),
        "state": "pending",
        "failureReason": item["reason"],
        "source": {
            "fileName": item["filename"],
            "episodeHint": episode_hint,
        },
        "actions": {
            "canRetryParse": auto_parse.get("status") == "parsed",
            "canManualPublish": True,
            "canDelete": True,
        },
    }
    if defaults.get("title") and episode_hint:
        detail["suggestedTarget"] = {
            "seriesTitle": str(defaults["title"]),
            "episodeLabel": episode_hint,
        }
    diagnostic_note = None
    if auto_parse.get("status") != "parsed":
        diagnostic_note = auto_parse.get("reason")
    if diagnostic_note:
        detail["diagnosticNote"] = diagnostic_note
    return detail


def retry_parse_review_item(review_item_id: str, *, locale: str | None = None) -> dict[str, Any]:
    main_module = runtime_main_module()
    item, item_path, review_root = main_module._manual_review_item_or_404(review_item_id)
    auto_parse = main_module._build_auto_parse_payload(item_path, review_root)
    parsed = auto_parse.get("parsed") if isinstance(auto_parse, dict) else None
    if auto_parse.get("status") != "parsed" or not isinstance(parsed, dict):
        raise HTTPException(
            status_code=422,
            detail=review_auto_parse_reason(auto_parse.get("reason"), locale)
            or auto_parse.get("reason")
            or "file is still not parseable",
        )

    media = main_module._manual_parsed_media(
        item=item,
        item_path=item_path,
        review_root=review_root,
        title=str(parsed["title"]),
        season=int(parsed["season"]),
        episode=int(parsed["episode"]),
    )
    result = main_module._publish_review_media(media, review_root=review_root)
    main_module.append_event(
        source="ops-review",
        level="success",
        action="retry-parse",
        message=f"Published from retry parse: {media.title} S{media.season:02d}E{media.episode:02d}",
        details={
            "source": str(media.relative_path),
            "target": result["target"],
        },
    )
    return {
        "ok": True,
        "action": "retry-parse",
        "reviewItemId": review_item_id,
        "message": _locale_text(
            locale,
            en="Published with the automatic parse result.",
            zh="已按自动解析结果发布。",
        ),
        "targetPath": result["target"],
    }


def manual_publish_review_item(
    review_item_id: str,
    *,
    locale: str | None = None,
    title: str | None = None,
    season: int | None = None,
    episode: int | None = None,
) -> dict[str, Any]:
    main_module = runtime_main_module()
    item, item_path, review_root = main_module._manual_review_item_or_404(review_item_id)
    auto_parse = main_module._build_auto_parse_payload(item_path, review_root)
    defaults = main_module._manual_publish_defaults(item, auto_parse)

    resolved_title = str(defaults.get("title") if title is None else title).strip()
    if not resolved_title:
        raise HTTPException(status_code=422, detail="title is required")

    resolved_season = defaults.get("season") if season is None else season
    resolved_episode = defaults.get("episode") if episode is None else episode
    if not isinstance(resolved_season, int) or resolved_season < 1:
        raise HTTPException(status_code=422, detail="season is required")
    if not isinstance(resolved_episode, int) or resolved_episode < 1:
        raise HTTPException(status_code=422, detail="episode is required")

    media = main_module._manual_parsed_media(
        item=item,
        item_path=item_path,
        review_root=review_root,
        title=resolved_title,
        season=resolved_season,
        episode=resolved_episode,
    )
    result = main_module._publish_review_media(media, review_root=review_root)
    main_module.append_event(
        source="ops-review",
        level="success",
        action="manual-publish",
        message=f"Manually published {resolved_title} S{resolved_season:02d}E{resolved_episode:02d}",
        details={
            "source": str(media.relative_path),
            "target": result["target"],
        },
    )
    return {
        "ok": True,
        "action": "manual-publish",
        "reviewItemId": review_item_id,
        "message": _locale_text(
            locale,
            en="Manual publish completed.",
            zh="已完成手动发布。",
        ),
        "targetPath": result["target"],
    }


def delete_review_item(review_item_id: str, *, locale: str | None = None) -> dict[str, Any]:
    main_module = runtime_main_module()
    item, item_path, review_root = main_module._manual_review_item_or_404(review_item_id)
    result = main_module._delete_review_file(item_path, review_root)
    main_module.append_event(
        source="ops-review",
        level="warning",
        action="delete",
        message=f"Deleted manual review file: {item['filename']}",
        details={
            "relative_path": item["relative_path"],
            "size": result["deleted_size_label"],
        },
    )
    return {
        "ok": True,
        "action": "delete",
        "reviewItemId": review_item_id,
        "message": _locale_text(
            locale,
            en="Review item deleted.",
            zh="已删除审核条目。",
        ),
        "deletedPath": result["deleted_path"],
    }
