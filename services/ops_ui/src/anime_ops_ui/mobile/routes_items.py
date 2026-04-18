from fastapi import APIRouter, Depends

from anime_ops_ui.mobile.auth import require_mobile_auth
from anime_ops_ui.services.mobile_detail_service import build_detail_payload

router = APIRouter(prefix="/api/mobile/items", tags=["mobile-items"], dependencies=[Depends(require_mobile_auth)])


@router.get("/{app_item_id}")
def get_item_detail(app_item_id: str) -> dict:
    return build_detail_payload(app_item_id)
