from datetime import date, timedelta

from anime_ops_ui.domain.mobile_models import CalendarDayBucket, CalendarDayItem


_DEFAULT_FOCUS_DATE = date(2026, 4, 18)
_WEEKDAY_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
_CALENDAR_ITEMS_BY_DATE = {
    "2026-04-13": [
        CalendarDayItem(
            appItemId="app_following_demo_3",
            title="有兽焉",
            posterUrl="https://example.com/poster-3.jpg",
            unread=True,
            availabilityState="mapped_unplayable",
        ),
        CalendarDayItem(
            appItemId="app_following_demo_unmapped",
            title="天官赐福",
            posterUrl="https://example.com/poster-6.jpg",
            unread=False,
            availabilityState="subscription_only",
        ),
    ],
    "2026-04-14": [
        CalendarDayItem(
            appItemId="app_following_demo_5",
            title="时光代理人",
            posterUrl="https://example.com/poster-5.jpg",
            unread=True,
            availabilityState="mapped_playable",
        )
    ],
    "2026-04-15": [],
    "2026-04-16": [
        CalendarDayItem(
            appItemId="app_following_demo_4",
            title="镇魂街 第一季",
            posterUrl="https://example.com/poster-4.jpg",
            unread=False,
            availabilityState="mapped_playable",
        )
    ],
    "2026-04-17": [
        CalendarDayItem(
            appItemId="app_following_demo_2",
            title="凡人修仙传",
            posterUrl="https://example.com/poster-2.jpg",
            unread=False,
            availabilityState="mapped_playable",
        ),
        CalendarDayItem(
            appItemId="app_following_demo_3",
            title="有兽焉",
            posterUrl="https://example.com/poster-3.jpg",
            unread=True,
            availabilityState="mapped_unplayable",
        ),
    ],
    "2026-04-18": [
        CalendarDayItem(
            appItemId="app_following_demo_1",
            title="灵笼 第一季",
            posterUrl="https://example.com/poster-1.jpg",
            unread=True,
            availabilityState="mapped_playable",
        ),
        CalendarDayItem(
            appItemId="app_following_demo_unmapped",
            title="天官赐福",
            posterUrl="https://example.com/poster-6.jpg",
            unread=False,
            availabilityState="subscription_only",
        ),
    ],
    "2026-04-19": [
        CalendarDayItem(
            appItemId="app_following_demo_5",
            title="时光代理人",
            posterUrl="https://example.com/poster-5.jpg",
            unread=True,
            availabilityState="mapped_playable",
        )
    ],
}


def build_calendar_payload(focus_date: str | None = None, window: int = 7) -> dict:
    focus = _parse_focus_date(focus_date)
    week_start = _start_of_week(focus)
    days = [_build_day_bucket(week_start + timedelta(days=index)) for index in range(7)]
    return {
        "focusDate": focus.isoformat(),
        "days": [bucket.model_dump() for bucket in days],
        "updatedAt": "2099-01-01T00:00:00Z",
    }


def _parse_focus_date(raw_focus_date: str | None) -> date:
    if not raw_focus_date:
        return _DEFAULT_FOCUS_DATE
    try:
        return date.fromisoformat(raw_focus_date)
    except ValueError:
        return _DEFAULT_FOCUS_DATE


def _start_of_week(target_date: date) -> date:
    return target_date - timedelta(days=target_date.weekday())


def _build_day_bucket(target_date: date) -> CalendarDayBucket:
    iso_date = target_date.isoformat()
    return CalendarDayBucket(
        date=iso_date,
        weekdayLabel=_WEEKDAY_LABELS[target_date.weekday()],
        dayLabel=target_date.strftime("%m/%d"),
        items=_CALENDAR_ITEMS_BY_DATE.get(iso_date, []),
    )
