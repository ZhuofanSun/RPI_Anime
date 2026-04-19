from fastapi import APIRouter, Query
from fastapi.responses import Response

from anime_ops_ui.services.mobile_media_service import proxy_mobile_poster

router = APIRouter(prefix="/api/mobile/media", tags=["mobile-media"])


@router.get("/poster")
def get_mobile_poster(
    path: str | None = Query(default=None, min_length=1, max_length=2048),
    jellyfinItemId: str | None = Query(default=None, min_length=1, max_length=256),
    sig: str = Query(..., min_length=16, max_length=128),
) -> Response:
    return proxy_mobile_poster(path=path, jellyfin_item_id=jellyfinItemId, sig=sig)
