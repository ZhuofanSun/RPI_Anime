from datetime import date, datetime, timezone

from anime_ops_ui.services.mobile_seasonal_service import build_calendar_buckets


def build_calendar_payload(
    focus_date: str | None = None,
    window: int = 7,
    *,
    now: datetime | None = None,
    public_host: str | None = None,
    public_base_url: str | None = None,
) -> dict:
    current = (now or datetime.now().astimezone()).astimezone()
    focus = _parse_focus_date(focus_date, now=current)
    days = build_calendar_buckets(focus_date=focus, public_host=public_host, public_base_url=public_base_url)
    return {
        "focusDate": focus.isoformat(),
        "days": [bucket.model_dump() for bucket in days],
        "updatedAt": current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _parse_focus_date(raw_focus_date: str | None, *, now: datetime | None = None) -> date:
    if not raw_focus_date:
        return _default_focus_date(now=now)
    try:
        return date.fromisoformat(raw_focus_date)
    except ValueError:
        return _default_focus_date(now=now)


def _default_focus_date(*, now: datetime | None = None) -> date:
    return (now or datetime.now().astimezone()).astimezone().date()
