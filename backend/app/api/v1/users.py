from fastapi import APIRouter

from app.api.dependencies import CurrentUserDependency, SessionDependency
from app.api.errors import ERROR_RESPONSES
from app.users.schemas import CurrentUserResponse, ProfilePayload, ProfileResponse
from app.users.service import UserService

router = APIRouter(tags=["users"], responses=ERROR_RESPONSES)


@router.get("/me", response_model=CurrentUserResponse)
async def get_me(user: CurrentUserDependency) -> CurrentUserResponse:
    return CurrentUserResponse(id=user.id, max_user_id=user.max_user_id)


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(
    user: CurrentUserDependency,
    session: SessionDependency,
) -> ProfileResponse:
    return await UserService(session).get_profile(user)


@router.put("/profile", response_model=ProfileResponse)
async def save_profile(
    payload: ProfilePayload,
    user: CurrentUserDependency,
    session: SessionDependency,
) -> ProfileResponse:
    return await UserService(session).save_profile(user, payload)

