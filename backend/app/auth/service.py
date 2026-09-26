import hmac

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.max_init_data import InitDataError, validate_init_data
from app.auth.schemas import AuthResponse
from app.auth.tokens import TokenError, issue_token, verify_subject
from app.core.config import settings
from app.core.exceptions import AuthUnavailableError, UnauthorizedError
from app.users.models import User
from app.users.repository import UserRepository
from app.users.schemas import CurrentUserResponse


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def login_with_max(self, init_data: str) -> AuthResponse:
        if not settings.max_bot_token or not settings.signing_key:
            raise AuthUnavailableError("MAX authentication is not configured")
        try:
            data = validate_init_data(
                init_data, settings.max_bot_token, settings.init_data_max_age_seconds
            )
        except InitDataError as error:
            raise UnauthorizedError("MAX init data is invalid") from error

        user = await self.get_or_create(data.user_id)
        token = issue_token(user.id, settings.signing_key, settings.access_token_ttl_seconds)
        return AuthResponse(
            access_token=token,
            expires_in=settings.access_token_ttl_seconds,
            start_param=data.start_param,
            user=CurrentUserResponse(id=user.id, max_user_id=user.max_user_id),
        )

    async def authenticate(self, authorization: str | None) -> User:
        if authorization:
            scheme, _, token = authorization.partition(" ")
            if scheme.lower() != "bearer" or not token:
                raise UnauthorizedError("Authorization header must use Bearer scheme")
            return await self._user_from_token(token.strip())

        if settings.dev_auth_enabled and not settings.is_production:
            return await self.get_or_create(settings.dev_max_user_id)
        raise UnauthorizedError("Authentication required")

    async def _user_from_token(self, token: str) -> User:
        for test_token, max_user_id in settings.test_access_tokens.items():
            # Compare bytes: str comparison raises on non-ASCII input instead of failing.
            if hmac.compare_digest(token.encode(), test_token.encode()):
                return await self.get_or_create(max_user_id)

        if not settings.signing_key:
            raise UnauthorizedError("Access token is invalid")
        try:
            subject = verify_subject(token, settings.signing_key)
        except TokenError as error:
            raise UnauthorizedError("Access token is invalid") from error
        if subject.max_user_id is not None:
            # Signed link from the bot chat: the bot already knows who the user is.
            return await self.get_or_create(subject.max_user_id)
        assert subject.user_id is not None
        user = await self.users.get(subject.user_id)
        if user is None:
            raise UnauthorizedError("Access token is invalid")
        return user

    async def get_or_create(self, max_user_id: int) -> User:
        user = await self.users.get_by_max_user_id(max_user_id)
        if user is None:
            user = await self.users.create_if_missing(max_user_id)
            await self.session.commit()
        return user
