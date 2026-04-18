from fastapi import APIRouter, Query, Request

from anime_ops_ui.i18n import resolve_locale
from anime_ops_ui.services.mobile_system_service import (
    build_system_downloads_payload,
    build_system_logs_payload,
    build_system_overview_payload,
)

router = APIRouter(prefix="/api/mobile/system", tags=["mobile-system"])


@router.get("/overview")
def get_system_overview(request: Request) -> dict:
    return build_system_overview_payload(locale=resolve_locale(request))


@router.get("/downloads")
def get_system_downloads(request: Request) -> dict:
    return build_system_downloads_payload(locale=resolve_locale(request))


@router.get("/logs")
def get_system_logs(
    request: Request,
    service: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=30),
) -> dict:
    normalized_service = None if service in {None, "", "all"} else service
    return build_system_logs_payload(locale=resolve_locale(request), service=normalized_service, limit=limit)
