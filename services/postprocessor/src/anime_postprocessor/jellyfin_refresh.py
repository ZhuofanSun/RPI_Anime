from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import requests

DEFAULT_REFRESH_USERNAME = "sunzhuofan"
DEFAULT_REFRESH_PASSWORD = "root1234"
_AUTHORIZATION_HEADER = (
    'MediaBrowser Client="RPIAnimePostprocessor", Device="anime-postprocessor", '
    'DeviceId="anime-postprocessor-jellyfin-refresh", Version="1.0.0"'
)


@dataclass(frozen=True)
class JellyfinSession:
    user_id: str
    access_token: str


def jellyfin_request_headers(
    access_token: str,
    *,
    json_body: bool = False,
) -> dict[str, str]:
    headers = {
        "X-Emby-Authorization": _AUTHORIZATION_HEADER,
        "X-Emby-Token": access_token,
    }
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def internal_jellyfin_base_url() -> str:
    explicit = str(os.environ.get("JELLYFIN_INTERNAL_BASE_URL", "")).strip()
    if explicit:
        return explicit.rstrip("/")
    port = int(os.environ.get("JELLYFIN_PORT", "8096"))
    return f"http://jellyfin:{port}"


def refresh_username() -> str:
    for env_name in ("JELLYFIN_REFRESH_USERNAME", "JELLYFIN_PLAYBACK_USERNAME"):
        candidate = str(os.environ.get(env_name, "")).strip()
        if candidate:
            return candidate
    return DEFAULT_REFRESH_USERNAME


def refresh_password() -> str:
    for env_name in ("JELLYFIN_REFRESH_PASSWORD", "JELLYFIN_PLAYBACK_PASSWORD"):
        candidate = str(os.environ.get(env_name, "")).strip()
        if candidate:
            return candidate
    return DEFAULT_REFRESH_PASSWORD


def authenticate_jellyfin_session() -> JellyfinSession:
    response = requests.post(
        f"{internal_jellyfin_base_url()}/Users/AuthenticateByName",
        headers={
            "Content-Type": "application/json",
            "X-Emby-Authorization": _AUTHORIZATION_HEADER,
        },
        json={
            "Username": refresh_username(),
            "Pw": refresh_password(),
        },
        timeout=10,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Jellyfin refresh authentication failed with status {response.status_code}."
        )

    payload = response.json()
    user = payload.get("User") or {}
    access_token = str(payload.get("AccessToken") or "").strip()
    user_id = str(user.get("Id") or "").strip()
    if not access_token or not user_id:
        raise RuntimeError("Jellyfin refresh authentication returned an incomplete session.")
    return JellyfinSession(user_id=user_id, access_token=access_token)


def derive_series_refresh_path(library_output_path: Path) -> Path:
    season_dir = library_output_path.parent
    if season_dir.name.lower().startswith("season "):
        return season_dir.parent
    return season_dir


def collect_series_updates(items: list[dict]) -> list[dict[str, str]]:
    updates_by_path: dict[str, dict[str, str]] = {}
    for item in items:
        path = str(item.get("jellyfin_refresh_path") or "").strip()
        if not path:
            continue
        update_type = str(item.get("jellyfin_refresh_update_type") or "Modified").strip()
        updates_by_path[path] = {
            "Path": path,
            "UpdateType": update_type or "Modified",
        }
    return list(updates_by_path.values())


def post_series_updates(
    updates: list[dict[str, str]],
    *,
    jellyfin_session: JellyfinSession | None = None,
) -> dict | None:
    if not updates:
        return None

    active_session = jellyfin_session or authenticate_jellyfin_session()
    response = requests.post(
        f"{internal_jellyfin_base_url()}/Library/Series/Updated",
        headers=jellyfin_request_headers(active_session.access_token, json_body=True),
        json={"Updates": updates},
        timeout=10,
    )
    if response.status_code not in {200, 204}:
        raise RuntimeError(
            f"Jellyfin series update notification failed with status {response.status_code}."
        )

    return {
        "endpoint": "/Library/Series/Updated",
        "path_count": len(updates),
        "update_types": sorted({item["UpdateType"] for item in updates}),
        "paths": [item["Path"] for item in updates],
    }
