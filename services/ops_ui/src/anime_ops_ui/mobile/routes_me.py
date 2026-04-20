from fastapi import APIRouter, Depends, Request

from anime_ops_ui import runtime_main_module
from anime_ops_ui.i18n import resolve_locale
from anime_ops_ui.mobile.auth import require_mobile_auth
from anime_ops_ui.services.mobile_me_service import build_me_context

router = APIRouter(prefix="/api/mobile/me", tags=["mobile-me"], dependencies=[Depends(require_mobile_auth)])


@router.get("/context")
def get_me_context(request: Request) -> dict:
    main_module = runtime_main_module()
    return build_me_context(
        locale=resolve_locale(request),
        public_host=main_module._public_host(request),
    )
