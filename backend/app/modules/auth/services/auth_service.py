from datetime import UTC, datetime
from uuid import UUID

import structlog

from backend.app.modules.auth.models import User, UserRole
from backend.app.modules.auth.repositories.user_repository import UserRepository
from backend.app.modules.auth.schemas.auth import (
    LoginRequest,
    TokenPair,
    UserCreate,
    UserPasswordReset,
    UserRead,
    UserUpdate,
)
from backend.app.modules.auth.security.hashing import hash_password, verify_password
from backend.app.modules.auth.security.jwt import create_access_token, create_refresh_token

logger = structlog.get_logger(__name__)


class AuthenticationError(Exception):
    pass


class InactiveUserError(Exception):
    pass


class UserManagementError(Exception):
    pass


class UserNotFoundError(Exception):
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

    async def list_users(self) -> list[UserRead]:
        return [UserRead.model_validate(user) for user in await self.repository.list()]

    async def create_user(self, payload: UserCreate) -> UserRead:
        if await self.repository.exists_by_username_or_email(payload.username, payload.email):
            raise UserManagementError("Username or email already exists")
        user = User(
            username=payload.username,
            email=payload.email,
            password_hash=hash_password(payload.password),
            role=payload.role,
            is_active=payload.is_active,
            is_superuser=payload.is_superuser,
        )
        await self.repository.create(user)
        await self.repository.session.commit()
        logger.info("auth.user_created", user_id=str(user.id), username=user.username, role=user.role.value)
        return UserRead.model_validate(user)

    async def update_user(self, user_id: UUID, payload: UserUpdate) -> UserRead:
        user = await self.repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError("User not found")
        update_data = payload.model_dump(exclude_unset=True)
        next_username = update_data.get("username")
        next_email = update_data.get("email")
        if next_username and next_username != user.username and await self.repository.get_by_username(next_username):
            raise UserManagementError("Username already exists")
        if next_email and next_email != user.email and await self.repository.get_by_email(next_email):
            raise UserManagementError("Email already exists")
        for key, value in update_data.items():
            setattr(user, key, value)
        await self.repository.session.commit()
        await self.repository.session.refresh(user)
        logger.info("auth.user_updated", user_id=str(user.id), fields=list(update_data.keys()))
        return UserRead.model_validate(user)

    async def reset_user_password(self, user_id: UUID, payload: UserPasswordReset) -> UserRead:
        user = await self.repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError("User not found")
        user.password_hash = hash_password(payload.password)
        await self.repository.session.commit()
        await self.repository.session.refresh(user)
        logger.info("auth.user_password_reset", user_id=str(user.id))
        return UserRead.model_validate(user)

    def _token_pair(self, user: User) -> TokenPair:
        return TokenPair(
            access_token=create_access_token(user),
            refresh_token=create_refresh_token(user),
            user=UserRead.model_validate(user),
        )
