from fastapi import APIRouter, Depends, Query, Request

from anime_ops_ui import runtime_main_module
from anime_ops_ui.mobile.auth import require_mobile_auth
from anime_ops_ui.services.mobile_calendar_service import build_calendar_payload

router = APIRouter(prefix="/api/mobile", tags=["mobile-calendar"], dependencies=[Depends(require_mobile_auth)])


@router.get("/calendar")
def get_calendar(
    request: Request,
    focus_date: str | None = Query(default=None, alias="focusDate"),
    window: int = Query(default=7, ge=3, le=14),
) -> dict:
    main_module = runtime_main_module()
    return build_calendar_payload(
        focus_date=focus_date,
        window=window,
        public_host=main_module._public_host(request),
        public_base_url=str(request.base_url).rstrip("/"),
    )
