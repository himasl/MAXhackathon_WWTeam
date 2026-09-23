from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import DevelopmentAuthDisabledError, ProfileNotFoundError
from app.users.models import User
from app.users.repository import UserRepository
from app.users.schemas import ProfilePayload, ProfileResponse, UserContext


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = UserRepository(session)

    async def get_development_user(self) -> User:
        if not settings.dev_auth_enabled or settings.app_env == "production":
            raise DevelopmentAuthDisabledError

        user = await self.repository.get_by_max_user_id(settings.dev_max_user_id)
        if user is None:
            user = await self.repository.create(settings.dev_max_user_id)
            await self.session.commit()
        return user

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
