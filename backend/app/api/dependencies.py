from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.users.models import User
from app.users.service import UserService

SessionDependency = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(session: SessionDependency) -> User:
    return await UserService(session).get_development_user()


CurrentUserDependency = Annotated[User, Depends(get_current_user)]

