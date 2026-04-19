from fastapi import APIRouter, Depends, Request

from anime_ops_ui.i18n import resolve_locale
from anime_ops_ui.mobile.auth import require_mobile_auth
from anime_ops_ui.services.mobile_me_service import build_me_context

router = APIRouter(prefix="/api/mobile/me", tags=["mobile-me"], dependencies=[Depends(require_mobile_auth)])


@router.get("/context")
def get_me_context(request: Request) -> dict:
    return build_me_context(locale=resolve_locale(request))
