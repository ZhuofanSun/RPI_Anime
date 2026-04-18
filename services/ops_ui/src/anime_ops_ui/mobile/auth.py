from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException, status

DEFAULT_EMBEDDED_USERNAME = "embedded-mobile-user"
DEFAULT_EMBEDDED_PASSWORD = "embedded-mobile-password"
DEFAULT_SESSION_TOKEN = "dev-mobile-session"
DEFAULT_EXPIRES_AT = "2099-01-01T00:00:00Z"


def embedded_username() -> str:
    return os.environ.get("OPS_MOBILE_EMBEDDED_USERNAME", DEFAULT_EMBEDDED_USERNAME)


def embedded_password() -> str:
    return os.environ.get("OPS_MOBILE_EMBEDDED_PASSWORD", DEFAULT_EMBEDDED_PASSWORD)


def session_token() -> str:
    return os.environ.get("OPS_MOBILE_SESSION_TOKEN", DEFAULT_SESSION_TOKEN)


def session_expires_at() -> str:
    return os.environ.get("OPS_MOBILE_SESSION_EXPIRES_AT", DEFAULT_EXPIRES_AT)


def create_mobile_session(username: str, password: str) -> dict:
    if not (
        hmac.compare_digest(username, embedded_username())
        and hmac.compare_digest(password, embedded_password())
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid embedded mobile credentials.",
        )

    return {
        "authenticated": True,
        "token": session_token(),
        "expiresAt": session_expires_at(),
    }


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def require_mobile_auth(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> str:
    token = _extract_bearer_token(authorization)
    if token is None or not hmac.compare_digest(token, session_token()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid mobile session token.",
        )
    return token
