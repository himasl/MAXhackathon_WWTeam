from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProfileNotFoundError
from app.users.models import User
from app.users.repository import UserRepository
from app.users.schemas import ProfilePayload, ProfileResponse, UserContext


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = UserRepository(session)

    async def get_profile(self, user: User) -> ProfileResponse:
        profile = await self.repository.get_profile(user.id)
        if profile is None:
            raise ProfileNotFoundError
        return ProfileResponse.model_validate(profile, from_attributes=True)

    async def save_profile(self, user: User, payload: ProfilePayload) -> ProfileResponse:
        profile = await self.repository.save_profile(user.id, payload)
        await self.session.commit()
        return ProfileResponse.model_validate(profile, from_attributes=True)

    async def get_context(self, user: User) -> UserContext:
        profile = await self.repository.get_profile(user.id)
        if profile is None:
            raise ProfileNotFoundError
        return UserContext.model_validate(profile, from_attributes=True)
