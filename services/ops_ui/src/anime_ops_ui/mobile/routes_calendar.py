from fastapi import APIRouter, Query

from anime_ops_ui.services.mobile_calendar_service import build_calendar_payload

router = APIRouter(prefix="/api/mobile", tags=["mobile-calendar"])


@router.get("/calendar")
def get_calendar(
    focus_date: str | None = Query(default=None, alias="focusDate"),
    window: int = Query(default=7, ge=3, le=14),
) -> dict:
    return build_calendar_payload(focus_date=focus_date, window=window)
