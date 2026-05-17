from datetime import UTC, datetime

import structlog

from backend.app.modules.auth.models import User, UserRole
from backend.app.modules.auth.repositories.user_repository import UserRepository
from backend.app.modules.auth.schemas.auth import LoginRequest, TokenPair, UserRead
from backend.app.modules.auth.security.hashing import hash_password, verify_password
from backend.app.modules.auth.security.jwt import create_access_token, create_refresh_token

logger = structlog.get_logger(__name__)


class AuthenticationError(Exception):
    pass


class InactiveUserError(Exception):
    pass


class AuthService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    async def login(self, payload: LoginRequest) -> TokenPair:
        user = await self.repository.get_by_login(payload.username_or_email)
        if user is None or not verify_password(payload.password, user.password_hash):
            logger.info("auth.login_failed", login=payload.username_or_email)
            raise AuthenticationError("Invalid username/email or password")

        if not user.is_active:
            logger.info("auth.login_inactive", user_id=str(user.id), username=user.username)
            raise InactiveUserError("User account is inactive")

        user.last_login_at = datetime.now(UTC)
        await self.repository.session.commit()
        await self.repository.session.refresh(user)
        logger.info("auth.login_success", user_id=str(user.id), username=user.username, role=user.role.value)
        return self._token_pair(user)

    async def refresh(self, user: User) -> TokenPair:
        if not user.is_active:
            raise InactiveUserError("User account is inactive")
        return self._token_pair(user)

    async def create_admin_if_missing(self, *, username: str, email: str, password: str) -> User | None:
        normalized_username = username.strip().lower()
        normalized_email = email.strip().lower()
        if not normalized_username or not normalized_email or not password:
            return None
        if await self.repository.exists_by_username_or_email(normalized_username, normalized_email):
            return None

        user = User(
            username=normalized_username,
            email=normalized_email,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
            is_superuser=True,
        )
        await self.repository.create(user)
        await self.repository.session.commit()
        logger.info("auth.bootstrap_admin_created", user_id=str(user.id), username=user.username)
        return user

    def _token_pair(self, user: User) -> TokenPair:
        return TokenPair(
            access_token=create_access_token(user),
            refresh_token=create_refresh_token(user),
            user=UserRead.model_validate(user),
        )
