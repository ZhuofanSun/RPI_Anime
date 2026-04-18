from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

from anime_ops_ui import runtime_main_module
from anime_ops_ui.domain.mobile_models import CalendarDayBucket, CalendarDayItem, HomeFollowingItem
from anime_ops_ui.services.weekly_schedule_service import build_phase4_schedule_snapshot

_CACHE_TTL_SECONDS = 15
_SNAPSHOT_CACHE: tuple[datetime, dict[str, Any]] | None = None


def build_seasonal_snapshot(*, now: datetime | None = None) -> dict[str, Any]:
    global _SNAPSHOT_CACHE

    current = (now or datetime.now().astimezone()).astimezone()
    cached = _SNAPSHOT_CACHE
    if cached is not None:
        cached_at, payload = cached
        if (current - cached_at).total_seconds() <= _CACHE_TTL_SECONDS:
            return payload

    snapshot = _build_snapshot(current)
    _SNAPSHOT_CACHE = (current, snapshot)
    return snapshot


def build_following_items(*, now: datetime | None = None) -> list[HomeFollowingItem]:
    snapshot = build_seasonal_snapshot(now=now)
    return [item["homeItem"] for item in snapshot["orderedItems"]]


def build_calendar_buckets(*, focus_date: date, now: datetime | None = None) -> list[CalendarDayBucket]:
    snapshot = build_seasonal_snapshot(now=now)
    week_start = _start_of_week(focus_date)

    buckets: list[CalendarDayBucket] = []
    for index, day in enumerate(snapshot["days"]):
        target_date = week_start + timedelta(days=index)
        buckets.append(
            CalendarDayBucket(
                date=target_date.isoformat(),
                weekdayLabel=str(day["weekdayLabel"]),
                dayLabel=target_date.strftime("%m/%d"),
                items=list(day["calendarItems"]),
            )
        )
    return buckets


def get_seasonal_item(app_item_id: str, *, now: datetime | None = None) -> dict[str, Any] | None:
    snapshot = build_seasonal_snapshot(now=now)
    return snapshot["itemsById"].get(app_item_id)


def build_recent_seasonal(
    *,
    exclude_app_item_id: str | None = None,
    limit: int = 6,
    now: datetime | None = None,
) -> list[dict[str, str]]:
    snapshot = build_seasonal_snapshot(now=now)
    items = [
        {
            "appItemId": item["appItemId"],
            "title": item["title"],
            "posterUrl": item["posterUrl"],
            "subtitle": item["recentSubtitle"],
        }
        for item in snapshot["orderedItems"]
        if item["appItemId"] != exclude_app_item_id
    ]
    return items[: max(limit, 0)]


def _build_snapshot(now: datetime) -> dict[str, Any]:
    main_module = runtime_main_module()
    anime_data_root = main_module.Path(main_module._env("ANIME_DATA_ROOT", "/srv/anime-data"))
    base_host = str(main_module._env("HOMEPAGE_BASE_HOST", main_module.socket.gethostname())).strip()
    autobangumi_port = int(main_module._env("AUTOBANGUMI_PORT", "7892"))
    jellyfin_port = int(main_module._env("JELLYFIN_PORT", "8096"))
    autobangumi_base_url = main_module._env("AUTOBANGUMI_API_URL", "").strip() or f"http://autobangumi:{autobangumi_port}"
    state_root = main_module.Path(main_module._env("OPS_UI_STATE_ROOT", "/data"))
    events = main_module.read_events(limit=300)

    try:
        raw_snapshot = build_phase4_schedule_snapshot(
            anime_data_root=anime_data_root,
            base_host=base_host,
            autobangumi_port=autobangumi_port,
            jellyfin_port=jellyfin_port,
            autobangumi_base_url=autobangumi_base_url,
            autobangumi_username=main_module._env("AUTOBANGUMI_USERNAME", ""),
            autobangumi_password=main_module._env("AUTOBANGUMI_PASSWORD", ""),
            state_root=state_root,
            now=now,
            events=events,
            visible_limit=50,
        )
    except Exception:
        return {
            "generatedAt": _iso_now(now),
            "days": [],
            "orderedItems": [],
            "itemsById": {},
        }

    days_payload = raw_snapshot.get("weekly_schedule", {}).get("days", [])
    ordered_items: list[dict[str, Any]] = []
    items_by_id: dict[str, dict[str, Any]] = {}
    days: list[dict[str, Any]] = []

    for day in days_payload:
        calendar_items: list[CalendarDayItem] = []
        raw_cards = list(day.get("items") or []) + list(day.get("hidden_items") or [])
        for card in raw_cards:
            mobile_item = _mobile_item_from_card(card)
            if mobile_item is None:
                continue
            ordered_items.append(mobile_item)
            items_by_id[mobile_item["appItemId"]] = mobile_item
            calendar_items.append(mobile_item["calendarItem"])

        days.append(
            {
                "weekday": day.get("weekday"),
                "weekdayLabel": day.get("label") or "",
                "calendarItems": calendar_items,
            }
        )

    return {
        "generatedAt": _iso_now(now),
        "days": days,
        "orderedItems": ordered_items,
        "itemsById": items_by_id,
    }


def _mobile_item_from_card(card: dict[str, Any]) -> dict[str, Any] | None:
    raw_id = card.get("id")
    if raw_id is None:
        return None

    app_item_id = _seasonal_app_item_id(raw_id)
    title = str(card.get("title") or "").strip() or "示例条目"
    poster_url = str(card.get("poster_url") or "").strip() or "https://example.com/poster.jpg"
    jellyfin_url = str(card.get("jellyfin_url") or "").strip() or None
    library_ready = bool(card.get("is_library_ready"))
    mapping_status = "mapped" if jellyfin_url or library_ready else "unmapped"
    availability_state = (
        "mapped_playable"
        if library_ready
        else "mapped_unplayable"
        if jellyfin_url
        else "subscription_only"
    )
    jellyfin_series_id = _extract_jellyfin_id(jellyfin_url)
    unread = library_ready
    detail = card.get("detail") if isinstance(card.get("detail"), dict) else {}

    return {
        "appItemId": app_item_id,
        "title": title,
        "posterUrl": poster_url,
        "mappingStatus": mapping_status,
        "availabilityState": availability_state,
        "jellyfinSeriesId": jellyfin_series_id,
        "unread": unread,
        "detail": detail,
        "homeItem": HomeFollowingItem(
            appItemId=app_item_id,
            title=title,
            posterUrl=poster_url,
            unread=unread,
            mappingStatus=mapping_status,
            jellyfinSeriesId=jellyfin_series_id,
            availabilityState=availability_state,
        ),
        "calendarItem": CalendarDayItem(
            appItemId=app_item_id,
            title=title,
            posterUrl=poster_url,
            unread=unread,
            availabilityState=availability_state,
        ),
        "recentSubtitle": "本周更新" if library_ready else "整理中",
    }


def _seasonal_app_item_id(card_id: int | str) -> str:
    return f"app_following_ab_{card_id}"


def _extract_jellyfin_id(jellyfin_url: str | None) -> str | None:
    if not jellyfin_url:
        return None
    parsed = urlparse(jellyfin_url)
    item_id = parse_qs(parsed.fragment.partition("?")[2]).get("id")
    if item_id:
        return item_id[0]
    query_id = parse_qs(parsed.query).get("id")
    if query_id:
        return query_id[0]
    return None


def _start_of_week(target_date: date) -> date:
    return target_date - timedelta(days=target_date.weekday())


def _iso_now(now: datetime) -> str:
    return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
