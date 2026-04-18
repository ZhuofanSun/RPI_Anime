from fastapi import APIRouter

from anime_ops_ui.services.mobile_home_service import build_favorites_payload, build_following_payload

router = APIRouter(prefix="/api/mobile/home", tags=["mobile-home"])


@router.get("/following")
def get_following() -> dict:
    return build_following_payload()


@router.get("/favorites")
def get_favorites() -> dict:
    return build_favorites_payload()
