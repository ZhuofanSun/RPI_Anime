from fastapi import APIRouter

router = APIRouter(prefix="/api/mobile/auth", tags=["mobile-auth"])


@router.post("/session")
def create_session(payload: dict) -> dict:
    return {
        "authenticated": True,
        "token": "dev-mobile-session",
        "expiresAt": "2099-01-01T00:00:00Z",
    }

