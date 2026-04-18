from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from anime_ops_ui.i18n import resolve_locale
from anime_ops_ui.services.mobile_rss_service import (
    analyze_rss_payload,
    build_rss_list_payload,
    delete_rss_payload,
    disable_rss_payload,
    enable_rss_payload,
    subscribe_rss_payload,
)

router = APIRouter(prefix="/api/mobile/rss", tags=["mobile-rss"])


class MobileRSSURLRequest(BaseModel):
    url: str = Field(min_length=1, max_length=1024)


@router.get("")
def get_rss_list(request: Request) -> dict:
    return build_rss_list_payload(locale=resolve_locale(request))


@router.post("/analyze")
def analyze_rss(request: Request, payload: MobileRSSURLRequest) -> dict:
    return analyze_rss_payload(
        url=payload.url,
        locale=resolve_locale(request),
        request_scheme=request.url.scheme,
        request_host=request.url.hostname or "127.0.0.1",
    )


@router.post("/subscribe")
def subscribe_rss(request: Request, payload: MobileRSSURLRequest) -> dict:
    return subscribe_rss_payload(url=payload.url, locale=resolve_locale(request))


@router.post("/{rss_id}/enable")
def enable_rss(rss_id: int, request: Request) -> dict:
    return enable_rss_payload(rss_id=rss_id, locale=resolve_locale(request))


@router.patch("/{rss_id}/disable")
def disable_rss(rss_id: int, request: Request) -> dict:
    return disable_rss_payload(rss_id=rss_id, locale=resolve_locale(request))


@router.delete("/{rss_id}")
def delete_rss(rss_id: int, request: Request) -> dict:
    return delete_rss_payload(rss_id=rss_id, locale=resolve_locale(request))
