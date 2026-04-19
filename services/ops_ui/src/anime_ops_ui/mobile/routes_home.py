from fastapi import APIRouter, Depends, Request

from anime_ops_ui import runtime_main_module
from anime_ops_ui.mobile.auth import require_mobile_auth
from anime_ops_ui.services.mobile_home_service import build_favorites_payload, build_following_payload

router = APIRouter(prefix="/api/mobile/home", tags=["mobile-home"], dependencies=[Depends(require_mobile_auth)])


@router.get("/following")
def get_following(request: Request) -> dict:
    main_module = runtime_main_module()
    return build_following_payload(
        public_host=main_module._public_host(request),
        public_base_url=str(request.base_url).rstrip("/"),
    )


@router.get("/favorites")
def get_favorites(request: Request) -> dict:
    return build_favorites_payload(
        public_base_url=str(request.base_url).rstrip("/"),
    )
