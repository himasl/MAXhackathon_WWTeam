from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import access
from app.admin.activity import record_activity
from app.auth.service import AuthService
from app.core.database import get_session
from app.core.exceptions import ForbiddenError
from app.users.models import User

SessionDependency = Annotated[AsyncSession, Depends(get_session)]

bearer_scheme = HTTPBearer(
    auto_error=False,
    description=(
        "Access token from POST /api/v1/auth/max, or a test token issued to reviewers."
    ),
)


async def get_current_user(
    session: SessionDependency,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    header = f"{credentials.scheme} {credentials.credentials}" if credentials else None
    user = await AuthService(session).authenticate(header)
    await record_activity(user.id, "app")
    return user


CurrentUserDependency = Annotated[User, Depends(get_current_user)]


def is_admin(user: User) -> bool:
    return user.max_user_id in access.admin_ids()


async def get_admin(user: CurrentUserDependency) -> User:
    if not is_admin(user):
        raise ForbiddenError()
    return user


AdminDependency = Annotated[User, Depends(get_admin)]


def get_language(accept_language: Annotated[str | None, Header()] = None) -> str:
    """"en" when the client asks for English (the interface language switch), else "ru"."""
    return "en" if (accept_language or "").lower().startswith("en") else "ru"


LanguageDependency = Annotated[str, Depends(get_language)]
