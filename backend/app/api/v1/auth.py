from fastapi import APIRouter

from app.api.dependencies import SessionDependency
from app.api.errors import ERROR_RESPONSES
from app.auth.schemas import AuthResponse, MaxAuthRequest
from app.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"], responses=ERROR_RESPONSES)


@router.post("/max", response_model=AuthResponse)
async def login_with_max(payload: MaxAuthRequest, session: SessionDependency) -> AuthResponse:
    """Exchange MAX Mini App ``initData`` for an access token.

    The backend validates the HMAC signature with the bot token and never trusts a
    ``user_id`` sent by the client.
    """
    return await AuthService(session).login_with_max(payload.init_data)
