from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
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

    async def get(self, user_id: UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def create_if_missing(self, max_user_id: int) -> User:
        """Insert concurrently-safe: a parallel first request must not fail with 500."""
        await self.session.execute(
            insert(User)
            .values(id=uuid4(), max_user_id=max_user_id)
            .on_conflict_do_nothing(index_elements=[User.max_user_id])
        )
        user = await self.get_by_max_user_id(max_user_id)
        assert user is not None
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
