from __future__ import annotations

import hashlib
import hmac
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import requests
from fastapi import HTTPException, status
from fastapi.responses import Response

from anime_ops_ui import runtime_main_module
from anime_ops_ui.mobile.auth import session_token
from anime_ops_ui.services.jellyfin_auth_service import (
    authenticate_jellyfin_session,
    internal_jellyfin_base_url,
    jellyfin_request_headers,
)


def build_mobile_poster_url(*, poster_link: str | None, public_base_url: str | None) -> str | None:
    normalized_path = _proxyable_poster_path(poster_link)
    if normalized_path is None:
        return str(poster_link or "").strip() or None

    base_url = str(public_base_url or "").strip().rstrip("/")
    if not base_url:
        return None

    return f"{base_url}/api/mobile/media/poster?{urlencode({'path': normalized_path, 'sig': sign_mobile_poster_path(normalized_path)})}"


def build_mobile_jellyfin_poster_url(*, jellyfin_item_id: str | None, public_base_url: str | None) -> str | None:
    normalized_item_id = _normalize_jellyfin_item_id(jellyfin_item_id)
    if normalized_item_id is None:
        return None

    base_url = str(public_base_url or "").strip().rstrip("/")
    if not base_url:
        return None

    return (
        f"{base_url}/api/mobile/media/poster?"
        f"{urlencode({'jellyfinItemId': normalized_item_id, 'sig': sign_mobile_jellyfin_item_id(normalized_item_id)})}"
    )


def build_mobile_trickplay_tile_url_template(
    *,
    jellyfin_item_id: str | None,
    media_source_id: str | None,
    width: int,
    public_base_url: str | None,
) -> str | None:
    normalized_item_id = _normalize_jellyfin_item_id(jellyfin_item_id)
    normalized_media_source_id = _normalize_trickplay_media_source_id(media_source_id)
    normalized_width = _normalize_trickplay_width(width)
    if normalized_item_id is None or normalized_media_source_id is None:
        return None

    base_url = str(public_base_url or "").strip().rstrip("/")
    if not base_url:
        return None

    query = urlencode(
        {
            "itemId": normalized_item_id,
            "mediaSourceId": normalized_media_source_id,
            "width": normalized_width,
            "index": "{index}",
            "sig": sign_mobile_trickplay_tile_set(
                item_id=normalized_item_id,
                media_source_id=normalized_media_source_id,
                width=normalized_width,
            ),
        }
    ).replace("%7Bindex%7D", "{index}")
    return f"{base_url}/api/mobile/media/trickplay/tile?{query}"


def sign_mobile_poster_path(path: str) -> str:
    normalized_path = _normalize_poster_path(path)
    return hmac.new(
        session_token().encode("utf-8"),
        normalized_path.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def sign_mobile_jellyfin_item_id(item_id: str) -> str:
    normalized_item_id = _normalize_jellyfin_item_id(item_id)
    if normalized_item_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Jellyfin item id.")
    return hmac.new(
        session_token().encode("utf-8"),
        normalized_item_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def sign_mobile_trickplay_tile_set(*, item_id: str, media_source_id: str, width: int) -> str:
    normalized_item_id = _normalize_jellyfin_item_id(item_id)
    normalized_media_source_id = _normalize_trickplay_media_source_id(media_source_id)
    normalized_width = _normalize_trickplay_width(width)
    if normalized_item_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Jellyfin item id.")
    if normalized_media_source_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing media source id.")
    payload = f"trickplay:{normalized_item_id}:{normalized_media_source_id}:{normalized_width}"
    return hmac.new(
        session_token().encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def proxy_mobile_poster(*, path: str | None = None, jellyfin_item_id: str | None = None, sig: str) -> Response:
    has_path = str(path or "").strip() != ""
    has_jellyfin_item_id = str(jellyfin_item_id or "").strip() != ""
    if has_path == has_jellyfin_item_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide exactly one poster target.",
        )

    if has_path:
        normalized_path = _normalize_poster_path(str(path))
        if not hmac.compare_digest(sig, sign_mobile_poster_path(normalized_path)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid poster signature.")
        upstream_urls = [_autobangumi_poster_url(normalized_path)]
    else:
        normalized_item_id = _normalize_jellyfin_item_id(jellyfin_item_id)
        if normalized_item_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Jellyfin item id.")
        if not hmac.compare_digest(sig, sign_mobile_jellyfin_item_id(normalized_item_id)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid poster signature.")
        upstream_urls = [_jellyfin_poster_url(normalized_item_id), *_jellyfin_fallback_poster_urls(normalized_item_id)]

    upstream = None
    not_found = False
    for upstream_url in upstream_urls:
        try:
            candidate = requests.get(upstream_url, timeout=10)
        except requests.RequestException as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to fetch poster asset: {exc}",
            ) from exc
        if candidate.status_code == 404:
            not_found = True
            continue
        if candidate.status_code >= 400:
            raise HTTPException(status_code=candidate.status_code, detail="Poster not available.")
        upstream = candidate
        break

    if upstream is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND if not_found else status.HTTP_502_BAD_GATEWAY, detail="Poster not available.")

    headers = {}
    for header in ("Cache-Control", "ETag", "Last-Modified", "Content-Length"):
        value = upstream.headers.get(header)
        if value:
            headers[header] = value
    headers.setdefault("Cache-Control", "public, max-age=3600")

    return Response(
        content=upstream.content,
        media_type=upstream.headers.get("Content-Type", "application/octet-stream"),
        headers=headers,
    )


def proxy_mobile_trickplay_tile(
    *,
    item_id: str | None,
    media_source_id: str | None,
    width: int,
    index: int,
    sig: str,
) -> Response:
    normalized_item_id = _normalize_jellyfin_item_id(item_id)
    normalized_media_source_id = _normalize_trickplay_media_source_id(media_source_id)
    normalized_width = _normalize_trickplay_width(width)
    normalized_index = _normalize_trickplay_tile_index(index)
    if normalized_item_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Jellyfin item id.")
    if normalized_media_source_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing media source id.")

    expected_sig = sign_mobile_trickplay_tile_set(
        item_id=normalized_item_id,
        media_source_id=normalized_media_source_id,
        width=normalized_width,
    )
    if not hmac.compare_digest(sig, expected_sig):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid trickplay signature.")

    jellyfin_session = authenticate_jellyfin_session()
    try:
        upstream = requests.get(
            f"{internal_jellyfin_base_url()}/Videos/{normalized_item_id}/Trickplay/{normalized_width}/{normalized_index}.jpg",
            params={"mediaSourceId": normalized_media_source_id},
            headers=jellyfin_request_headers(jellyfin_session.access_token),
            timeout=10,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch trickplay tile: {exc}",
        ) from exc

    if upstream.status_code == 404:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trickplay tile not available.")
    if upstream.status_code >= 400:
        raise HTTPException(status_code=upstream.status_code, detail="Trickplay tile not available.")

    headers = {}
    for header in ("Cache-Control", "ETag", "Last-Modified", "Content-Length"):
        value = upstream.headers.get(header)
        if value:
            headers[header] = value
    headers.setdefault("Cache-Control", "public, max-age=86400")

    return Response(
        content=upstream.content,
        media_type=upstream.headers.get("Content-Type", "image/jpeg"),
        headers=headers,
    )


def _proxyable_poster_path(poster_link: str | None) -> str | None:
    raw_value = str(poster_link or "").strip()
    if not raw_value:
        return None

    parsed = urlsplit(raw_value)
    if parsed.scheme or parsed.netloc:
        if not _looks_like_autobangumi_asset_url(parsed):
            return None
        path = parsed.path
        if parsed.query:
            path = f"{path}?{parsed.query}"
        return _normalize_poster_path(path)

    return _normalize_poster_path(raw_value)


def _looks_like_autobangumi_asset_url(parsed) -> bool:
    main_module = runtime_main_module()
    autobangumi_port = int(main_module._env("AUTOBANGUMI_PORT", "7892"))
    if parsed.port == autobangumi_port:
        return True
    return (parsed.hostname or "").strip().lower() == "autobangumi"


def _normalize_poster_path(path: str) -> str:
    normalized = str(path or "").strip()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing poster path.")
    if "://" in normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Poster path must be relative.")

    parsed = urlsplit(normalized)
    if parsed.netloc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Poster path must not include a host.")

    clean_path = parsed.path.lstrip("/")
    path_segments = [segment for segment in clean_path.split("/") if segment not in {"", "."}]
    if not path_segments or any(segment == ".." for segment in path_segments):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid poster path.")

    normalized_path = "/".join(path_segments)
    if parsed.query:
        normalized_path = f"{normalized_path}?{parsed.query}"
    return normalized_path


def _normalize_jellyfin_item_id(item_id: str | None) -> str | None:
    normalized = str(item_id or "").strip()
    if not normalized:
        return None
    if not re.fullmatch(r"[A-Za-z0-9-]+", normalized):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Jellyfin item id.")
    return normalized


def _normalize_trickplay_media_source_id(media_source_id: str | None) -> str | None:
    normalized = str(media_source_id or "").strip()
    if not normalized:
        return None
    if not re.fullmatch(r"[A-Za-z0-9._-]+", normalized):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid media source id.")
    return normalized


def _normalize_trickplay_width(width: int | str | None) -> int:
    try:
        normalized = int(width or 0)
    except (TypeError, ValueError):
        normalized = 0
    if normalized <= 0 or normalized > 8192:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid trickplay width.")
    return normalized


def _normalize_trickplay_tile_index(index: int | str | None) -> int:
    try:
        normalized = int(index or 0)
    except (TypeError, ValueError):
        normalized = -1
    if normalized < 0 or normalized > 1_000_000:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid trickplay tile index.")
    return normalized


def _autobangumi_poster_url(path: str) -> str:
    main_module = runtime_main_module()
    autobangumi_port = int(main_module._env("AUTOBANGUMI_PORT", "7892"))
    configured_base = str(main_module._env("AUTOBANGUMI_API_URL", "")).strip()
    if configured_base:
        parsed = urlsplit(configured_base)
        asset_base = f"{parsed.scheme or 'http'}://{parsed.netloc}".rstrip("/")
    else:
        asset_base = f"http://autobangumi:{autobangumi_port}"
    return f"{asset_base.rstrip('/')}/{path.lstrip('/')}"


def _jellyfin_poster_url(item_id: str) -> str:
    main_module = runtime_main_module()
    jellyfin_port = int(main_module._env("JELLYFIN_PORT", "8096"))
    return f"http://jellyfin:{jellyfin_port}/Items/{item_id}/Images/Primary"


def _jellyfin_fallback_poster_urls(item_id: str) -> list[str]:
    fallback_item_ids = _jellyfin_fallback_item_ids(item_id)
    return [_jellyfin_poster_url(fallback_item_id) for fallback_item_id in fallback_item_ids if fallback_item_id != item_id]


def _jellyfin_fallback_item_ids(item_id: str) -> list[str]:
    db_path = _jellyfin_db_path()
    if not db_path.exists():
        return []

    try:
        with sqlite3.connect(db_path) as conn:
            season_row = conn.execute(
                """
                SELECT Id
                FROM BaseItems
                WHERE Type = ?
                    AND SeriesId = ?
                ORDER BY COALESCE(IndexNumber, 0), Id
                LIMIT 1
                """,
                ("MediaBrowser.Controller.Entities.TV.Season", item_id),
            ).fetchone()
            episode_row = conn.execute(
                """
                SELECT Id
                FROM BaseItems
                WHERE Type = ?
                    AND SeriesId = ?
                ORDER BY COALESCE(ParentIndexNumber, 0), COALESCE(IndexNumber, 0), Id
                LIMIT 1
                """,
                ("MediaBrowser.Controller.Entities.TV.Episode", item_id),
            ).fetchone()
    except sqlite3.Error:
        return []

    fallbacks: list[str] = []
    if season_row is not None and season_row[0] is not None:
        fallbacks.append(str(season_row[0]))
    if episode_row is not None and episode_row[0] is not None:
        fallbacks.append(str(episode_row[0]))
    return fallbacks


def _jellyfin_db_path() -> Path:
    main_module = runtime_main_module()
    anime_data_root = main_module.Path(main_module._env("ANIME_DATA_ROOT", "/srv/anime-data"))
    return anime_data_root / "appdata" / "jellyfin" / "config" / "data" / "jellyfin.db"
