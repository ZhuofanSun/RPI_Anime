from fastapi import APIRouter, Body, Request
from pydantic import BaseModel, Field

from anime_ops_ui.i18n import resolve_locale
from anime_ops_ui.services.mobile_review_service import (
    build_review_detail_payload,
    build_review_queue_payload,
    delete_review_item,
    manual_publish_review_item,
    retry_parse_review_item,
)

router = APIRouter(prefix="/api/mobile/review", tags=["mobile-review"])


class MobileManualPublishRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    season: int | None = Field(default=None, ge=1, le=99)
    episode: int | None = Field(default=None, ge=1, le=999)


@router.get("")
def get_review_queue(request: Request) -> dict:
    return build_review_queue_payload(locale=resolve_locale(request))


@router.get("/{review_item_id}")
def get_review_detail(review_item_id: str, request: Request) -> dict:
    return build_review_detail_payload(review_item_id, locale=resolve_locale(request))


@router.post("/{review_item_id}/retry-parse")
def retry_review_parse(review_item_id: str, request: Request) -> dict:
    return retry_parse_review_item(review_item_id, locale=resolve_locale(request))


@router.post("/{review_item_id}/manual-publish")
def manual_publish_review(
    review_item_id: str,
    request: Request,
    payload: MobileManualPublishRequest | None = Body(default=None),
) -> dict:
    return manual_publish_review_item(
        review_item_id,
        locale=resolve_locale(request),
        title=payload.title if payload is not None else None,
        season=payload.season if payload is not None else None,
        episode=payload.episode if payload is not None else None,
    )


@router.delete("/{review_item_id}")
def delete_review(review_item_id: str, request: Request) -> dict:
    return delete_review_item(review_item_id, locale=resolve_locale(request))
