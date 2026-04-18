from fastapi import APIRouter, Request

from anime_ops_ui.i18n import resolve_locale
from anime_ops_ui.services.mobile_system_service import build_system_overview_payload

router = APIRouter(prefix="/api/mobile/system", tags=["mobile-system"])


@router.get("/overview")
def get_system_overview(request: Request) -> dict:
    return build_system_overview_payload(locale=resolve_locale(request))
