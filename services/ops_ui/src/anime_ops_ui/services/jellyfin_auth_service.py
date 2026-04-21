from __future__ import annotations

import os
from dataclasses import dataclass

import requests
from fastapi import HTTPException, status

from anime_ops_ui import runtime_main_module

DEFAULT_PLAYBACK_USERNAME = "sunzhuofan"
DEFAULT_PLAYBACK_PASSWORD = "root1234"
_AUTHORIZATION_HEADER = (
    'MediaBrowser Client="NekoYa", Device="NekoYaMobile", DeviceId="nekoya-mobile-playback", Version="1.0.0"'
)


@dataclass(frozen=True)
class JellyfinSession:
    user_id: str
    access_token: str


def internal_jellyfin_base_url() -> str:
    main_module = runtime_main_module()
    explicit = str(main_module._env("JELLYFIN_INTERNAL_BASE_URL", "")).strip()
    if explicit:
        return explicit.rstrip("/")
    port = int(main_module._env("JELLYFIN_PORT", "8096"))
    return f"http://jellyfin:{port}"


def playback_username() -> str:
    return os.environ.get("JELLYFIN_PLAYBACK_USERNAME", DEFAULT_PLAYBACK_USERNAME)


def playback_password() -> str:
    return os.environ.get("JELLYFIN_PLAYBACK_PASSWORD", DEFAULT_PLAYBACK_PASSWORD)


def authenticate_jellyfin_session() -> JellyfinSession:
    response = requests.post(
        f"{internal_jellyfin_base_url()}/Users/AuthenticateByName",
        headers={
            "Content-Type": "application/json",
            "X-Emby-Authorization": _AUTHORIZATION_HEADER,
        },
        json={
            "Username": playback_username(),
            "Pw": playback_password(),
        },
        timeout=10,
    )
    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Jellyfin playback authentication failed.",
        )

    payload = response.json()
    user = payload.get("User") or {}
    access_token = str(payload.get("AccessToken") or "").strip()
    user_id = str(user.get("Id") or "").strip()
    if not access_token or not user_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Jellyfin playback authentication returned an incomplete session.",
        )
    return JellyfinSession(user_id=user_id, access_token=access_token)
