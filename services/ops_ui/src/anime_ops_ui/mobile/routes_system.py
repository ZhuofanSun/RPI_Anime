from fastapi import APIRouter, Query, Request

from anime_ops_ui.i18n import resolve_locale
from anime_ops_ui.services.mobile_system_service import (
    build_system_downloads_payload,
    build_system_logs_payload,
    build_system_overview_payload,
    build_system_tailscale_payload,
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
    limit: int = Query(default=30, ge=1, le=30),
) -> dict:
    return build_system_logs_payload(locale=resolve_locale(request), limit=limit)


@router.get("/tailscale")
def get_system_tailscale(request: Request) -> dict:
    return build_system_tailscale_payload(locale=resolve_locale(request))
