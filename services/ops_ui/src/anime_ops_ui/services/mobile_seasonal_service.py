from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

from anime_ops_ui import runtime_main_module
from anime_ops_ui.domain.mobile_models import CalendarDayBucket, CalendarDayItem, HomeFollowingItem
from anime_ops_ui.services.mobile_media_service import build_mobile_poster_url
from anime_ops_ui.services.weekly_schedule_service import build_phase4_schedule_snapshot

_CACHE_TTL_SECONDS = 15
_SNAPSHOT_CACHE: dict[str, tuple[datetime, dict[str, Any]]] | None = None


def build_seasonal_snapshot(
    *,
    now: datetime | None = None,
    public_host: str | None = None,
    public_base_url: str | None = None,
) -> dict[str, Any]:
    global _SNAPSHOT_CACHE

    current = (now or datetime.now().astimezone()).astimezone()
    cache_key = str(public_base_url or public_host or "").strip().lower()
    cache = _SNAPSHOT_CACHE or {}
    cached = cache.get(cache_key)
    if cached is not None:
        cached_at, payload = cached
        if (current - cached_at).total_seconds() <= _CACHE_TTL_SECONDS:
            return payload

    snapshot = _build_snapshot(current, public_host=public_host, public_base_url=public_base_url)
    cache[cache_key] = (current, snapshot)
    _SNAPSHOT_CACHE = cache
    return snapshot


def build_following_items(
    *,
    now: datetime | None = None,
    public_host: str | None = None,
    public_base_url: str | None = None,
) -> list[HomeFollowingItem]:
    snapshot = build_seasonal_snapshot(now=now, public_host=public_host, public_base_url=public_base_url)
    return [item["homeItem"] for item in snapshot["orderedItems"]]


def build_calendar_buckets(
    *,
    focus_date: date,
    now: datetime | None = None,
    public_host: str | None = None,
    public_base_url: str | None = None,
) -> list[CalendarDayBucket]:
    snapshot = build_seasonal_snapshot(now=now, public_host=public_host, public_base_url=public_base_url)
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


def get_seasonal_item(
    app_item_id: str,
    *,
    now: datetime | None = None,
    public_host: str | None = None,
    public_base_url: str | None = None,
) -> dict[str, Any] | None:
    snapshot = build_seasonal_snapshot(now=now, public_host=public_host, public_base_url=public_base_url)
    return snapshot["itemsById"].get(app_item_id)


def build_recent_seasonal(
    *,
    exclude_app_item_id: str | None = None,
    limit: int = 6,
    now: datetime | None = None,
    public_host: str | None = None,
    public_base_url: str | None = None,
) -> list[dict[str, str]]:
    snapshot = build_seasonal_snapshot(now=now, public_host=public_host, public_base_url=public_base_url)
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


def _build_snapshot(
    now: datetime,
    *,
    public_host: str | None = None,
    public_base_url: str | None = None,
) -> dict[str, Any]:
    main_module = runtime_main_module()
    anime_data_root = main_module.Path(main_module._env("ANIME_DATA_ROOT", "/srv/anime-data"))
    base_host = str(public_host or main_module._env("HOMEPAGE_BASE_HOST", main_module.socket.gethostname())).strip()
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
        weekday_label = str(day.get("label") or "").strip()
        calendar_items: list[CalendarDayItem] = []
        raw_cards = list(day.get("items") or []) + list(day.get("hidden_items") or [])
        for card in raw_cards:
            mobile_item = _mobile_item_from_card(
                card,
                public_base_url=public_base_url,
                weekday_label=weekday_label,
            )
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


def _mobile_item_from_card(
    card: dict[str, Any],
    *,
    public_base_url: str | None = None,
    weekday_label: str | None = None,
) -> dict[str, Any] | None:
    raw_id = card.get("id")
    if raw_id is None:
        return None

    app_item_id = _seasonal_app_item_id(raw_id)
    title = str(card.get("title") or "").strip() or "示例条目"
    poster_url = build_mobile_poster_url(
        poster_link=str(card.get("poster_url") or "").strip() or None,
        public_base_url=public_base_url,
    ) or "https://example.com/poster.jpg"
    jellyfin_url = str(card.get("jellyfin_url") or "").strip() or None
    jellyfin_series_id = _extract_jellyfin_id(jellyfin_url)
    has_series_mapping = jellyfin_series_id is not None
    library_ready = bool(card.get("is_library_ready"))
    mapping_status = "mapped" if has_series_mapping else "unmapped"
    availability_state = (
        "mapped_playable" if has_series_mapping and library_ready
        else "mapped_unplayable" if has_series_mapping
        else "subscription_only"
    )
    unread = has_series_mapping and library_ready
    detail = card.get("detail") if isinstance(card.get("detail"), dict) else {}
    recent_subtitle = _recent_subtitle(
        weekday_label=weekday_label,
        availability_state=availability_state,
    )

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
        "recentSubtitle": recent_subtitle,
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


def _recent_subtitle(*, weekday_label: str | None, availability_state: str) -> str:
    normalized_label = str(weekday_label or "").strip()
    if availability_state == "mapped_playable":
        return f"{normalized_label}更新" if normalized_label else "已更新"
    if availability_state == "mapped_unplayable":
        return f"{normalized_label}放送" if normalized_label else "待整理"
    return "待映射"


def _start_of_week(target_date: date) -> date:
    return target_date - timedelta(days=target_date.weekday())


def _iso_now(now: datetime) -> str:
    return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
