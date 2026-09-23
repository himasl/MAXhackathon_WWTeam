from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import AuthService
from app.core.database import get_session
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
    return await AuthService(session).authenticate(header)


CurrentUserDependency = Annotated[User, Depends(get_current_user)]
