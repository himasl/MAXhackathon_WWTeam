from typing import Literal

from fastapi import APIRouter, status
from fastapi.responses import Response
from pydantic import BaseModel

from app.api.dependencies import (
    CurrentUserDependency,
    LanguageDependency,
    SessionDependency,
    is_admin,
)
from app.api.errors import ERROR_RESPONSES
from app.users.schemas import CurrentUserResponse, ProfilePayload, ProfileResponse
from app.users.service import UserService

router = APIRouter(tags=["users"], responses=ERROR_RESPONSES)


@router.get("/me", response_model=CurrentUserResponse)
async def get_me(user: CurrentUserDependency) -> CurrentUserResponse:
    return CurrentUserResponse(id=user.id, max_user_id=user.max_user_id, is_admin=is_admin(user))


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
    lang: LanguageDependency,
) -> ProfileResponse:
    user.lang = lang  # bot messages follow the interface language
    return await UserService(session).save_profile(user, payload)


class LanguagePayload(BaseModel):
    lang: Literal["ru", "en"]


@router.put("/me/language", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def set_language(
    payload: LanguagePayload, user: CurrentUserDependency, session: SessionDependency
) -> Response:
    """The interface language; the bot writes to the user in it too."""
    user.lang = payload.lang
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
