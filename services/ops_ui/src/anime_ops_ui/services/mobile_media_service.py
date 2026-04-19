from __future__ import annotations

import hashlib
import hmac
from urllib.parse import urlencode, urlsplit

import requests
from fastapi import HTTPException, status
from fastapi.responses import Response

from anime_ops_ui import runtime_main_module
from anime_ops_ui.mobile.auth import session_token


def build_mobile_poster_url(*, poster_link: str | None, public_base_url: str | None) -> str | None:
    normalized_path = _proxyable_poster_path(poster_link)
    if normalized_path is None:
        return str(poster_link or "").strip() or None

    base_url = str(public_base_url or "").strip().rstrip("/")
    if not base_url:
        return None

    return f"{base_url}/api/mobile/media/poster?{urlencode({'path': normalized_path, 'sig': sign_mobile_poster_path(normalized_path)})}"


def sign_mobile_poster_path(path: str) -> str:
    normalized_path = _normalize_poster_path(path)
    return hmac.new(
        session_token().encode("utf-8"),
        normalized_path.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def proxy_mobile_poster(*, path: str, sig: str) -> Response:
    normalized_path = _normalize_poster_path(path)
    if not hmac.compare_digest(sig, sign_mobile_poster_path(normalized_path)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid poster signature.")

    upstream_url = _autobangumi_poster_url(normalized_path)
    try:
        upstream = requests.get(upstream_url, timeout=10)
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch poster from AutoBangumi: {exc}",
        ) from exc

    if upstream.status_code >= 400:
        raise HTTPException(status_code=upstream.status_code, detail="Poster not available.")

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
