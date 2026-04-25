from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import quote, urlencode, urlparse

import requests
from fastapi import HTTPException, status

from anime_ops_ui import runtime_main_module
from anime_ops_ui.services.mobile_detail_service import build_detail_payload
from anime_ops_ui.services.mobile_media_service import build_mobile_trickplay_tile_url_template
from anime_ops_ui.services.jellyfin_auth_service import (
    JellyfinSession,
    authenticate_jellyfin_session,
    internal_jellyfin_base_url,
    jellyfin_request_headers,
)

_TEXT_SUBTITLE_CODECS = {
    "ass",
    "mov_text",
    "movtext",
    "ssa",
    "srt",
    "subrip",
    "text",
    "ttml",
    "tx3g",
    "vtt",
    "webvtt",
}

def build_playback_bootstrap_payload(
    app_item_id: str,
    *,
    app_episode_id: str | None = None,
    app_season_id: str | None = None,
    public_host: str | None = None,
    public_base_url: str | None = None,
) -> dict[str, Any]:
    detail_payload = build_detail_payload(
        app_item_id,
        public_host=public_host,
        public_base_url=public_base_url,
    )
    selection = _resolve_playback_selection(
        detail_payload,
        app_episode_id=app_episode_id,
        app_season_id=app_season_id,
    )

    jellyfin_session = authenticate_jellyfin_session()
    jellyfin_item = fetch_jellyfin_item_detail(
        jellyfin_session.user_id,
        selection["jellyfinEpisodeId"],
        jellyfin_session.access_token,
    )
    playback_info = fetch_jellyfin_playback_info(
        jellyfin_session.user_id,
        selection["jellyfinEpisodeId"],
        jellyfin_session.access_token,
    )

    public_jellyfin_base = public_jellyfin_base_url(public_base_url)
    media_sources = build_media_sources_payload(
        playback_info=playback_info,
        jellyfin_item=jellyfin_item,
        jellyfin_item_id=selection["jellyfinEpisodeId"],
        public_jellyfin_base=public_jellyfin_base,
        public_base_url=public_base_url,
        access_token=jellyfin_session.access_token,
    )
    default_media_source_id = media_sources[0]["id"] if media_sources else None

    return {
        "target": {
            "appItemId": app_item_id,
            "appSeasonId": selection["appSeasonId"],
            "appEpisodeId": selection["appEpisodeId"],
            "jellyfinSeriesId": selection["jellyfinSeriesId"],
            "jellyfinSeasonId": selection["jellyfinSeasonId"],
            "jellyfinEpisodeId": selection["jellyfinEpisodeId"],
            "title": str(detail_payload.get("title") or ""),
            "episodeLabel": selection["episodeLabel"],
            "durationTicks": int(jellyfin_item.get("RunTimeTicks") or 0),
            "resumeTicks": int((jellyfin_item.get("UserData") or {}).get("PlaybackPositionTicks") or 0),
        },
        "transport": {
            "provider": "jellyfin",
            "mode": "directJellyfin",
            "authMode": "queryApiKey",
            "baseUrl": public_jellyfin_base,
        },
        "defaultMediaSourceId": default_media_source_id,
        "jellyfinPlaySessionId": str(playback_info.get("PlaySessionId") or ""),
        "mediaSources": media_sources,
        "reporting": {
            "kind": "backendBridge",
            "startUrl": f"/api/mobile/items/{app_item_id}/playback/session/start",
            "progressUrl": f"/api/mobile/items/{app_item_id}/playback/session/progress",
            "stopUrl": f"/api/mobile/items/{app_item_id}/playback/session/stop",
            "heartbeatIntervalSeconds": 5,
        },
    }


def create_playback_session_payload(
    app_item_id: str,
    *,
    app_episode_id: str | None = None,
    app_season_id: str | None = None,
    media_source_id: str | None = None,
    audio_track_id: str | None = None,
    subtitle_track_id: str | None = None,
    preferred_delivery: str | None = None,
    public_host: str | None = None,
    public_base_url: str | None = None,
) -> dict[str, Any]:
    bootstrap = build_playback_bootstrap_payload(
        app_item_id,
        app_episode_id=app_episode_id,
        app_season_id=app_season_id,
        public_host=public_host,
        public_base_url=public_base_url,
    )
    media_sources = list(bootstrap.get("mediaSources") or [])
    selected_source = next(
        (source for source in media_sources if source["id"] == media_source_id),
        None,
    )
    if selected_source is None and media_sources:
        selected_source = media_sources[0]
    if selected_source is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Playable media source unavailable for mobile item: {app_item_id}",
        )

    selected_audio_track_id = normalize_audio_track_id(selected_source, audio_track_id)
    selected_subtitle_track_id = normalize_subtitle_track_id(selected_source, subtitle_track_id)
    delivery = resolve_stream_delivery(
        selected_source,
        preferred_delivery=preferred_delivery,
    )
    session_id = str(bootstrap.get("jellyfinPlaySessionId") or uuid.uuid4().hex)
    stream_url = resolve_direct_stream_url(selected_source, delivery=delivery)

    return {
        "sessionId": session_id,
        "target": bootstrap["target"],
        "stream": {
            "delivery": delivery,
            "url": stream_url,
            "headers": {},
        },
        "selectedMediaSourceId": selected_source["id"],
        "selectedAudioTrackId": selected_audio_track_id,
        "selectedSubtitleTrackId": selected_subtitle_track_id,
        "resumeTicks": bootstrap["target"]["resumeTicks"],
        "durationTicks": bootstrap["target"]["durationTicks"],
        "reporting": bootstrap["reporting"],
    }


def build_reporting_ack(
    app_item_id: str,
    *,
    phase: str,
    session_id: str | None = None,
    position_ticks: int | None = None,
    jellyfin_episode_id: str | None = None,
    media_source_id: str | None = None,
    audio_track_id: str | None = None,
    subtitle_track_id: str | None = None,
    play_method: str | None = None,
    is_paused: bool | None = None,
    failed: bool | None = None,
    completed: bool | None = None,
    public_host: str | None = None,
    public_base_url: str | None = None,
) -> dict[str, Any]:
    normalized_phase = str(phase or "").strip().lower()
    if normalized_phase in {"start", "progress", "stop"}:
        normalized_episode_id = resolve_reporting_episode_id(
            app_item_id,
            jellyfin_episode_id=jellyfin_episode_id,
            public_host=public_host,
            public_base_url=public_base_url,
        )
        jellyfin_session = authenticate_jellyfin_session()
        if normalized_phase != "stop" or not completed:
            post_jellyfin_playback_position(
            item_id=normalized_episode_id,
            user_id=jellyfin_session.user_id,
            session_id=session_id,
            position_ticks=position_ticks,
            media_source_id=media_source_id,
            audio_track_id=audio_track_id,
            subtitle_track_id=subtitle_track_id,
            play_method=play_method,
            is_paused=is_paused,
            failed=failed,
            access_token=jellyfin_session.access_token,
            )
        if normalized_phase == "stop" and completed:
            post_jellyfin_mark_played(
                item_id=normalized_episode_id,
                user_id=jellyfin_session.user_id,
                access_token=jellyfin_session.access_token,
            )
    return {
        "ok": True,
        "appItemId": app_item_id,
        "phase": phase,
        "sessionId": session_id,
        "positionTicks": position_ticks,
    }


def mark_jellyfin_item_played(
    app_item_id: str,
    *,
    jellyfin_episode_id: str | None = None,
    jellyfin_session: JellyfinSession | None = None,
    public_host: str | None = None,
    public_base_url: str | None = None,
) -> None:
    normalized_episode_id = resolve_reporting_episode_id(
        app_item_id,
        jellyfin_episode_id=jellyfin_episode_id,
        public_host=public_host,
        public_base_url=public_base_url,
    )
    active_session = jellyfin_session or authenticate_jellyfin_session()
    post_jellyfin_mark_played(
        item_id=normalized_episode_id,
        user_id=active_session.user_id,
        access_token=active_session.access_token,
    )


def resolve_reporting_episode_id(
    app_item_id: str,
    *,
    jellyfin_episode_id: str | None = None,
    public_host: str | None = None,
    public_base_url: str | None = None,
) -> str:
    detail_payload = build_detail_payload(
        app_item_id,
        public_host=public_host,
        public_base_url=public_base_url,
    )
    selection = _resolve_playback_selection(detail_payload)

    normalized_episode_id = str(jellyfin_episode_id or "").strip() or str(selection["jellyfinEpisodeId"] or "").strip()
    if not normalized_episode_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mobile playback reporting target is incomplete for item: {app_item_id}",
        )
    return normalized_episode_id


def post_jellyfin_mark_played(*, item_id: str, user_id: str, access_token: str) -> None:
    response = requests.post(
        f"{internal_jellyfin_base_url()}/UserPlayedItems/{item_id}",
        params={"userId": user_id},
        headers=jellyfin_request_headers(access_token),
        timeout=10,
    )
    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Jellyfin played-state update failed for mobile playback.",
        )


def post_jellyfin_playback_position(
    *,
    item_id: str,
    user_id: str,
    access_token: str,
    session_id: str | None = None,
    position_ticks: int | None = None,
    media_source_id: str | None = None,
    audio_track_id: str | None = None,
    subtitle_track_id: str | None = None,
    play_method: str | None = None,
    is_paused: bool | None = None,
    failed: bool | None = None,
) -> None:
    response = requests.post(
        f"{internal_jellyfin_base_url()}/UserItems/{item_id}/UserData",
        params={"userId": user_id},
        headers=jellyfin_request_headers(access_token, json_body=True),
        json={"PlaybackPositionTicks": max(int(position_ticks or 0), 0)},
        timeout=10,
    )
    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Jellyfin playback-position update failed.",
        )


def fetch_jellyfin_item_detail(user_id: str, jellyfin_item_id: str, access_token: str) -> dict[str, Any]:
    response = requests.get(
        f"{internal_jellyfin_base_url()}/Users/{user_id}/Items/{jellyfin_item_id}",
        headers={"X-Emby-Token": access_token},
        timeout=10,
    )
    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Jellyfin item lookup failed for mobile playback.",
        )
    return response.json()


def fetch_jellyfin_playback_info(
    user_id: str,
    jellyfin_item_id: str,
    access_token: str,
    *,
    playback_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = requests.post(
        f"{internal_jellyfin_base_url()}/Items/{jellyfin_item_id}/PlaybackInfo",
        params={"UserId": user_id},
        headers={
            "Content-Type": "application/json",
            "X-Emby-Token": access_token,
        },
        json=playback_request or {},
        timeout=10,
    )
    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Jellyfin playback-info lookup failed for mobile playback.",
        )
    return response.json()


def build_media_sources_payload(
    *,
    playback_info: dict[str, Any],
    jellyfin_item: dict[str, Any] | None = None,
    jellyfin_item_id: str,
    public_jellyfin_base: str,
    public_base_url: str | None = None,
    access_token: str,
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for source in playback_info.get("MediaSources") or []:
        source_id = str(source.get("Id") or "").strip()
        if not source_id:
            continue

        audio_tracks: list[dict[str, Any]] = []
        subtitle_tracks: list[dict[str, Any]] = [
            {
                "id": "subtitle:off",
                "languageCode": None,
                "displayName": "Off",
                "isDefault": False,
                "delivery": "none",
                "format": None,
                "streamIndex": None,
                "streamUrl": None,
                "streamFormat": None,
            }
        ]

        default_audio_track_id: str | None = None
        default_subtitle_track_id: str | None = None
        default_audio_index = source.get("DefaultAudioStreamIndex")

        for stream in source.get("MediaStreams") or []:
            stream_type = str(stream.get("Type") or "")
            stream_index = stream.get("Index")
            if stream_index is None:
                continue

            if stream_type == "Audio":
                track_id = f"audio:{stream_index}"
                is_default = bool(stream.get("IsDefault")) or stream_index == default_audio_index
                if is_default and default_audio_track_id is None:
                    default_audio_track_id = track_id
                audio_tracks.append(
                    {
                        "id": track_id,
                        "languageCode": stream.get("Language"),
                        "displayName": stream.get("DisplayTitle") or f"Audio {stream_index}",
                        "isDefault": is_default,
                        "codec": stream.get("Codec"),
                        "channelLayout": stream.get("ChannelLayout"),
                        "streamIndex": stream_index,
                    }
                )
                continue

            is_subtitle = stream_type == "Subtitle" or bool(stream.get("IsTextSubtitleStream"))
            if is_subtitle:
                track_id = f"subtitle:{stream_index}"
                is_default = bool(stream.get("IsDefault"))
                stream_format = subtitle_stream_format(stream)
                if is_default and default_subtitle_track_id is None:
                    default_subtitle_track_id = track_id
                subtitle_tracks.append(
                    {
                        "id": track_id,
                        "languageCode": stream.get("Language"),
                        "displayName": stream.get("DisplayTitle") or stream.get("Title") or f"Subtitle {stream_index}",
                        "isDefault": is_default,
                        "delivery": "external" if stream.get("IsExternal") else "embedded",
                        "format": stream.get("Codec"),
                        "streamIndex": stream_index,
                        "streamUrl": build_subtitle_stream_url(
                            public_jellyfin_base,
                            jellyfin_item_id=jellyfin_item_id,
                            media_source_id=source_id,
                            stream_index=stream_index,
                            access_token=access_token,
                            route_format=stream_format,
                        )
                        if stream_format
                        else None,
                        "streamFormat": stream_format,
                    }
                )

        if default_audio_track_id is None and audio_tracks:
            default_audio_track_id = audio_tracks[0]["id"]
            audio_tracks[0]["isDefault"] = True
        if default_subtitle_track_id is None:
            default_subtitle_track_id = next(
                (track["id"] for track in subtitle_tracks if track["isDefault"]),
                "subtitle:off",
            )

        sources.append(
            {
                "id": source_id,
                "name": source.get("Name") or source_id,
                "container": source.get("Container"),
                "videoCodec": first_media_stream_value(source, stream_type="Video", key="Codec"),
                "width": first_media_stream_value(source, stream_type="Video", key="Width"),
                "height": first_media_stream_value(source, stream_type="Video", key="Height"),
                "bitrate": source.get("Bitrate"),
                "supportsDirectPlay": bool(source.get("SupportsDirectPlay")),
                "supportsDirectStream": bool(source.get("SupportsDirectStream")),
                "defaultAudioTrackId": default_audio_track_id,
                "defaultSubtitleTrackId": default_subtitle_track_id,
                "directPlayUrl": build_direct_play_url(
                    public_jellyfin_base,
                    jellyfin_item_id=jellyfin_item_id,
                    media_source_id=source_id,
                    access_token=access_token,
                ),
                "trickplay": build_trickplay_payload(
                    jellyfin_item=jellyfin_item or {},
                    jellyfin_item_id=jellyfin_item_id,
                    media_source_id=source_id,
                    public_base_url=public_base_url,
                ),
                "audioTracks": audio_tracks,
                "subtitleTracks": subtitle_tracks,
            }
        )

    return sources


def resolve_stream_delivery(
    source: dict[str, Any],
    *,
    preferred_delivery: str | None = None,
) -> str:
    preferred = str(preferred_delivery or "").strip()

    if preferred in {"directPlay", "directStream"} and source.get("directPlayUrl"):
        return preferred
    if source.get("supportsDirectPlay") and source.get("directPlayUrl"):
        return "directPlay"
    if source.get("supportsDirectStream") and source.get("directPlayUrl"):
        return "directStream"
    if source.get("directPlayUrl"):
        return "directPlay"

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="No direct mobile stream delivery found for the selected media source.",
    )


def normalize_audio_track_id(source: dict[str, Any], track_id: str | None) -> str | None:
    requested = str(track_id or "").strip()
    if requested and any(track["id"] == requested for track in source.get("audioTracks") or []):
        return requested
    return source.get("defaultAudioTrackId")


def normalize_subtitle_track_id(source: dict[str, Any], track_id: str | None) -> str | None:
    requested = str(track_id or "").strip()
    if requested and any(track["id"] == requested for track in source.get("subtitleTracks") or []):
        return requested
    return source.get("defaultSubtitleTrackId")


def resolve_direct_stream_url(source: dict[str, Any], *, delivery: str) -> str:
    direct_play_url = source.get("directPlayUrl")
    if delivery in {"directPlay", "directStream"} and direct_play_url:
        return str(direct_play_url)
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Selected direct playback delivery is unavailable.",
    )


def build_direct_play_url(
    public_jellyfin_base: str,
    *,
    jellyfin_item_id: str,
    media_source_id: str,
    access_token: str,
) -> str:
    return (
        f"{public_jellyfin_base}/Videos/{jellyfin_item_id}/stream"
        f"?static=true&MediaSourceId={media_source_id}&api_key={access_token}"
    )


def subtitle_stream_format(stream: dict[str, Any]) -> str | None:
    codec = str(stream.get("Codec") or "").strip().lower()
    if bool(stream.get("IsTextSubtitleStream")) or codec in _TEXT_SUBTITLE_CODECS:
        return "vtt"
    return None


def build_subtitle_stream_url(
    public_jellyfin_base: str,
    *,
    jellyfin_item_id: str,
    media_source_id: str,
    stream_index: int,
    access_token: str,
    route_format: str,
) -> str:
    item_id = quote(str(jellyfin_item_id), safe="")
    source_id = quote(str(media_source_id), safe="")
    index = quote(str(stream_index), safe="")
    normalized_format = quote(str(route_format).strip().lstrip("."), safe="")
    query = urlencode({"api_key": access_token})
    return (
        f"{public_jellyfin_base}/Videos/{item_id}/{source_id}/"
        f"Subtitles/{index}/0/Stream.{normalized_format}?{query}"
    )


def build_trickplay_payload(
    *,
    jellyfin_item: dict[str, Any],
    jellyfin_item_id: str,
    media_source_id: str,
    public_base_url: str | None,
) -> dict[str, Any] | None:
    info = select_trickplay_info(jellyfin_item.get("Trickplay"), media_source_id=media_source_id)
    if info is None:
        return None

    width = _int_field(info, "Width", "width")
    height = _int_field(info, "Height", "height")
    tile_columns = _int_field(info, "TileWidth", "tileWidth")
    tile_rows = _int_field(info, "TileHeight", "tileHeight")
    thumbnail_count = _int_field(info, "ThumbnailCount", "thumbnailCount")
    interval = _int_field(info, "Interval", "interval")
    if min(width, height, tile_columns, tile_rows, thumbnail_count, interval) <= 0:
        return None

    tile_url_template = build_mobile_trickplay_tile_url_template(
        jellyfin_item_id=jellyfin_item_id,
        media_source_id=media_source_id,
        width=width,
        public_base_url=public_base_url,
    )
    if tile_url_template is None:
        return None

    return {
        "state": "available",
        "source": "jellyfin",
        "itemId": jellyfin_item_id,
        "mediaSourceId": media_source_id,
        "width": width,
        "thumbnailWidth": width,
        "thumbnailHeight": height,
        "tileColumns": tile_columns,
        "tileRows": tile_rows,
        "thumbnailCount": thumbnail_count,
        "intervalMilliseconds": interval,
        "tileUrlTemplate": tile_url_template,
    }


def select_trickplay_info(trickplay: Any, *, media_source_id: str) -> dict[str, Any] | None:
    candidates: list[tuple[tuple[str, ...], dict[str, Any]]] = []
    _collect_trickplay_candidates(trickplay, path=(), candidates=candidates)
    if not candidates:
        return None

    def sort_key(candidate: tuple[tuple[str, ...], dict[str, Any]]) -> tuple[int, int, int]:
        path, info = candidate
        path_matches_source = media_source_id in path
        width = _int_field(info, "Width", "width")
        preferred_width_penalty = abs(width - 320) if width else 10_000
        valid_penalty = 0 if _is_valid_trickplay_info(info) else 1
        return (valid_penalty, 0 if path_matches_source else 1, preferred_width_penalty)

    selected = min(candidates, key=sort_key)[1]
    return selected if _is_valid_trickplay_info(selected) else None


def _collect_trickplay_candidates(
    value: Any,
    *,
    path: tuple[str, ...],
    candidates: list[tuple[tuple[str, ...], dict[str, Any]]],
) -> None:
    if not isinstance(value, dict):
        return
    if any(key in value for key in ("Width", "width")) and any(
        key in value for key in ("ThumbnailCount", "thumbnailCount")
    ):
        candidates.append((path, value))
        return
    for key, child in value.items():
        _collect_trickplay_candidates(child, path=(*path, str(key)), candidates=candidates)


def _is_valid_trickplay_info(info: dict[str, Any]) -> bool:
    return (
        _int_field(info, "Width", "width") > 0
        and _int_field(info, "Height", "height") > 0
        and _int_field(info, "TileWidth", "tileWidth") > 0
        and _int_field(info, "TileHeight", "tileHeight") > 0
        and _int_field(info, "ThumbnailCount", "thumbnailCount") > 0
        and _int_field(info, "Interval", "interval") > 0
    )


def _int_field(payload: dict[str, Any], *keys: str) -> int:
    for key in keys:
        try:
            value = int(payload.get(key) or 0)
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            return value
    return 0


def first_media_stream_value(source: dict[str, Any], *, stream_type: str, key: str) -> Any | None:
    for stream in source.get("MediaStreams") or []:
        if str(stream.get("Type") or "") == stream_type:
            return stream.get(key)
    return None


def public_jellyfin_base_url(public_base_url: str | None) -> str:
    normalized_base_url = str(public_base_url or "").strip()
    parsed = urlparse(normalized_base_url)
    host = parsed.hostname
    if not host:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing public host for mobile playback.",
        )
    main_module = runtime_main_module()
    jellyfin_port = int(main_module._env("JELLYFIN_PORT", "8096"))
    return f"http://{host}:{jellyfin_port}"


def _resolve_playback_selection(
    detail_payload: dict[str, Any],
    *,
    app_episode_id: str | None = None,
    app_season_id: str | None = None,
) -> dict[str, str | None]:
    playback = detail_payload.get("playback")
    hero_state = str(detail_payload.get("heroState") or "")
    if hero_state != "playable_primed" or not isinstance(playback, dict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mobile item is not currently playable: {detail_payload.get('appItemId')}",
        )

    episodes = list(detail_payload.get("episodes") or [])
    seasons = list(detail_payload.get("seasons") or [])
    requested_episode_id = str(app_episode_id or "").strip()
    requested_season_id = str(app_season_id or "").strip()

    selected_episode = next((episode for episode in episodes if episode.get("id") == requested_episode_id), None)
    selected_season = next((season for season in seasons if season.get("id") == requested_season_id), None)

    if selected_episode is None and selected_season is not None:
        season_episodes = [episode for episode in episodes if episode.get("seasonId") == selected_season.get("id")]
        selected_episode = next((episode for episode in season_episodes if episode.get("focused")), None)
        if selected_episode is None and season_episodes:
            selected_episode = season_episodes[-1]

    if selected_episode is None and requested_episode_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown mobile playback episode: {requested_episode_id}",
        )

    if selected_episode is None:
        default_episode_id = str(playback.get("appDefaultEpisodeId") or "").strip()
        selected_episode = next((episode for episode in episodes if episode.get("id") == default_episode_id), None)
        if selected_episode is None:
            selected_episode = next((episode for episode in episodes if episode.get("focused")), None)
        if selected_episode is None and episodes:
            selected_episode = episodes[-1]

    if selected_episode is not None and selected_season is None:
        selected_season = next((season for season in seasons if season.get("id") == selected_episode.get("seasonId")), None)

    if selected_season is None:
        default_season_id = str(playback.get("appDefaultSeasonId") or "").strip()
        selected_season = next((season for season in seasons if season.get("id") == default_season_id), None)
        if selected_season is None:
            selected_season = next((season for season in seasons if season.get("selected")), None)
        if selected_season is None and seasons:
            selected_season = seasons[-1]

    jellyfin_episode_id = str(
        (selected_episode or {}).get("jellyfinEpisodeId")
        or (detail_payload.get("hero") or {}).get("latestPlayableJellyfinEpisodeId")
        or playback.get("defaultEpisodeId")
        or ""
    ).strip()
    jellyfin_season_id = str(
        (selected_episode or {}).get("jellyfinSeasonId")
        or (selected_season or {}).get("jellyfinSeasonId")
        or playback.get("defaultSeasonId")
        or ""
    ).strip()
    jellyfin_series_id = str(
        (selected_episode or {}).get("jellyfinSeriesId")
        or (selected_season or {}).get("jellyfinSeriesId")
        or playback.get("seriesId")
        or ""
    ).strip()
    if not jellyfin_episode_id or not jellyfin_series_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mobile playback target is incomplete for item: {detail_payload.get('appItemId')}",
        )

    return {
        "appSeasonId": (selected_season or {}).get("id") or playback.get("appDefaultSeasonId"),
        "appEpisodeId": (selected_episode or {}).get("id") or playback.get("appDefaultEpisodeId"),
        "jellyfinSeriesId": jellyfin_series_id,
        "jellyfinSeasonId": jellyfin_season_id or None,
        "jellyfinEpisodeId": jellyfin_episode_id,
        "episodeLabel": (selected_episode or {}).get("label") or (detail_payload.get("hero") or {}).get("primedLabel"),
    }
