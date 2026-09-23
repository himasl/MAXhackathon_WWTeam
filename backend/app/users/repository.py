from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import User, UserProfile
from app.users.schemas import ProfilePayload


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_max_user_id(self, max_user_id: int) -> User | None:
        return cast(
            User | None,
            await self.session.scalar(select(User).where(User.max_user_id == max_user_id)),
        )

    async def create(self, max_user_id: int) -> User:
        user = User(max_user_id=max_user_id)
        self.session.add(user)
        await self.session.flush()
        return user

    async def lock(self, user_id: UUID) -> None:
        await self.session.scalar(select(User).where(User.id == user_id).with_for_update())

    async def get_profile(self, user_id: UUID) -> UserProfile | None:
        return cast(
            UserProfile | None,
            await self.session.scalar(
                select(UserProfile).where(UserProfile.user_id == user_id)
            ),
        )

    async def save_profile(self, user_id: UUID, payload: ProfilePayload) -> UserProfile:
        profile = await self.get_profile(user_id)
        values = payload.model_dump()
        if profile is None:
            profile = UserProfile(user_id=user_id, **values)
            self.session.add(profile)
        else:
            for field, value in values.items():
                setattr(profile, field, value)
        await self.session.flush()
        return profile
