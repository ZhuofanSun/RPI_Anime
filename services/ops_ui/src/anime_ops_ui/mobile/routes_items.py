from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from anime_ops_ui import runtime_main_module
from anime_ops_ui.mobile.auth import require_mobile_auth
from anime_ops_ui.services.mobile_detail_service import build_detail_payload
from anime_ops_ui.services.mobile_playback_service import (
    build_playback_bootstrap_payload,
    build_reporting_ack,
    create_playback_session_payload,
)

router = APIRouter(prefix="/api/mobile/items", tags=["mobile-items"], dependencies=[Depends(require_mobile_auth)])


class MobilePlaybackSessionRequest(BaseModel):
    appEpisodeId: str | None = None
    appSeasonId: str | None = None
    mediaSourceId: str | None = None
    audioTrackId: str | None = None
    subtitleTrackId: str | None = None
    preferredDelivery: str | None = None


class MobilePlaybackReportingRequest(BaseModel):
    sessionId: str | None = None
    positionTicks: int | None = None


@router.get("/{app_item_id}/playback")
def get_item_playback(
    app_item_id: str,
    request: Request,
    episodeId: str | None = None,
    seasonId: str | None = None,
) -> dict:
    main_module = runtime_main_module()
    return build_playback_bootstrap_payload(
        app_item_id,
        app_episode_id=episodeId,
        app_season_id=seasonId,
        public_host=main_module._public_host(request),
        public_base_url=str(request.base_url).rstrip("/"),
    )


@router.post("/{app_item_id}/playback/session")
def create_item_playback_session(
    app_item_id: str,
    payload: MobilePlaybackSessionRequest,
    request: Request,
) -> dict:
    main_module = runtime_main_module()
    return create_playback_session_payload(
        app_item_id,
        app_episode_id=payload.appEpisodeId,
        app_season_id=payload.appSeasonId,
        media_source_id=payload.mediaSourceId,
        audio_track_id=payload.audioTrackId,
        subtitle_track_id=payload.subtitleTrackId,
        preferred_delivery=payload.preferredDelivery,
        public_host=main_module._public_host(request),
        public_base_url=str(request.base_url).rstrip("/"),
    )


@router.post("/{app_item_id}/playback/session/start")
def report_item_playback_session_started(app_item_id: str, payload: MobilePlaybackReportingRequest) -> dict:
    return build_reporting_ack(
        app_item_id,
        phase="start",
        session_id=payload.sessionId,
        position_ticks=payload.positionTicks,
    )


@router.post("/{app_item_id}/playback/session/progress")
def report_item_playback_session_progress(app_item_id: str, payload: MobilePlaybackReportingRequest) -> dict:
    return build_reporting_ack(
        app_item_id,
        phase="progress",
        session_id=payload.sessionId,
        position_ticks=payload.positionTicks,
    )


@router.post("/{app_item_id}/playback/session/stop")
def report_item_playback_session_stopped(app_item_id: str, payload: MobilePlaybackReportingRequest) -> dict:
    return build_reporting_ack(
        app_item_id,
        phase="stop",
        session_id=payload.sessionId,
        position_ticks=payload.positionTicks,
    )


@router.get("/{app_item_id}")
def get_item_detail(app_item_id: str, request: Request) -> dict:
    main_module = runtime_main_module()
    return build_detail_payload(
        app_item_id,
        public_host=main_module._public_host(request),
        public_base_url=str(request.base_url).rstrip("/"),
    )
