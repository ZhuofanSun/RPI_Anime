from datetime import date, datetime, timezone

from anime_ops_ui.services.mobile_seasonal_service import build_calendar_buckets


_DEFAULT_FOCUS_DATE = date(2026, 4, 18)


def build_calendar_payload(
    focus_date: str | None = None,
    window: int = 7,
    *,
    public_host: str | None = None,
    public_base_url: str | None = None,
) -> dict:
    focus = _parse_focus_date(focus_date)
    days = build_calendar_buckets(focus_date=focus, public_host=public_host, public_base_url=public_base_url)
    return {
        "focusDate": focus.isoformat(),
        "days": [bucket.model_dump() for bucket in days],
        "updatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _parse_focus_date(raw_focus_date: str | None) -> date:
    if not raw_focus_date:
        return _DEFAULT_FOCUS_DATE
    try:
        return date.fromisoformat(raw_focus_date)
    except ValueError:
        return _DEFAULT_FOCUS_DATE
