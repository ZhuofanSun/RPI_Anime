from fastapi import APIRouter
from pydantic import BaseModel, Field

from anime_ops_ui.mobile.auth import create_mobile_session


router = APIRouter(prefix="/api/mobile/auth", tags=["mobile-auth"])


class MobileAuthBootstrapRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=128)


@router.post("/session")
def create_session(payload: MobileAuthBootstrapRequest) -> dict:
    return create_mobile_session(payload.username, payload.password)
