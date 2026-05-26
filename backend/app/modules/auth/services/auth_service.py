from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_hex
from uuid import UUID

import structlog

from backend.app.core.config import settings
from backend.app.modules.auth.models import RefreshTokenSession, User, UserRole
from backend.app.modules.auth.repositories.user_repository import RefreshTokenSessionRepository, UserRepository
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


class RefreshTokenReplayError(Exception):
    pass


class UserManagementError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class AuthService:
    def __init__(
        self,
        repository: UserRepository,
        refresh_repository: RefreshTokenSessionRepository | None = None,
    ) -> None:
        self.repository = repository
        self.refresh_repository = refresh_repository or RefreshTokenSessionRepository(repository.session)

    async def login(
        self,
        payload: LoginRequest,
        *,
        user_agent: str | None = None,
        source_ip: str | None = None,
    ) -> TokenPair:
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
        return await self._token_pair(user, user_agent=user_agent, source_ip=source_ip)

    async def refresh(
        self,
        user: User,
        *,
        refresh_session: RefreshTokenSession,
        user_agent: str | None = None,
        source_ip: str | None = None,
    ) -> TokenPair:
        if not user.is_active:
            raise InactiveUserError("User account is inactive")
        now = datetime.now(UTC)
        refresh_session.revoked_at = now
        refresh_session.revoke_reason = "rotated"
        refresh_session.last_used_at = now
        refresh_session.last_activity_at = now
        await self.repository.session.commit()
        return await self._token_pair(
            user,
            family_id=refresh_session.family_id,
            user_agent=user_agent,
            source_ip=source_ip,
        )

    async def revoke_user_tokens(self, user: User) -> None:
        user.token_version += 1
        now = datetime.now(UTC)
        for session in await self.refresh_repository.list_active_for_user(user.id):
            session.revoked_at = now
            session.revoke_reason = "logout_all"
        await self.repository.session.commit()

    async def revoke_current_session(self, user: User, session_id: UUID | None) -> None:
        if session_id is None:
            await self.revoke_user_tokens(user)
            return
        session = await self.refresh_repository.get_by_id(session_id)
        if session and session.user_id == user.id and session.revoked_at is None:
            session.revoked_at = datetime.now(UTC)
            session.revoke_reason = "logout"
            await self.repository.session.commit()

    async def validate_refresh_session(self, *, token_payload: dict[str, object], refresh_token: str) -> RefreshTokenSession:
        token_id = str(token_payload.get("jti") or "")
        family_id = str(token_payload.get("family") or "")
        if not token_id or not family_id:
            raise AuthenticationError("Invalid refresh token")
        session = await self.refresh_repository.get_by_token_id(token_id)
        if session is None:
            raise AuthenticationError("Invalid refresh token")
        if session.token_hash != self._hash_token(refresh_token):
            await self.revoke_refresh_family(session.user_id, family_id, reason="refresh_token_hash_mismatch")
            raise RefreshTokenReplayError("Refresh token replay detected")
        now = datetime.now(UTC)
        if session.revoked_at is not None:
            await self.revoke_refresh_family(session.user_id, family_id, reason="refresh_token_reuse")
            raise RefreshTokenReplayError("Refresh token replay detected")
        if self._aware(session.expires_at) <= now:
            session.revoked_at = now
            session.revoke_reason = "expired"
            await self.repository.session.commit()
            raise AuthenticationError("Refresh token expired")
        if self._aware(session.last_activity_at) + timedelta(minutes=settings.session_inactivity_timeout_minutes) <= now:
            session.revoked_at = now
            session.revoke_reason = "inactive"
            await self.repository.session.commit()
            raise AuthenticationError("Session expired due to inactivity")
        return session

    async def revoke_refresh_family(self, user_id: UUID, family_id: str, *, reason: str) -> None:
        now = datetime.now(UTC)
        for session in await self.refresh_repository.list_family(user_id, family_id):
            if session.revoked_at is None:
                session.revoked_at = now
            session.revoke_reason = reason
        user = await self.repository.get_by_id(user_id)
        if user is not None:
            user.token_version += 1
        await self.repository.session.commit()

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
        if {"role", "is_active", "is_superuser"} & set(update_data):
            user.token_version += 1
        await self.repository.session.commit()
        await self.repository.session.refresh(user)
        logger.info("auth.user_updated", user_id=str(user.id), fields=list(update_data.keys()))
        return UserRead.model_validate(user)

    async def reset_user_password(self, user_id: UUID, payload: UserPasswordReset) -> UserRead:
        user = await self.repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError("User not found")
        user.password_hash = hash_password(payload.password)
        user.token_version += 1
        await self.repository.session.commit()
        await self.repository.session.refresh(user)
        logger.info("auth.user_password_reset", user_id=str(user.id))
        return UserRead.model_validate(user)

    async def _token_pair(
        self,
        user: User,
        *,
        family_id: str | None = None,
        user_agent: str | None = None,
        source_ip: str | None = None,
    ) -> TokenPair:
        now = datetime.now(UTC)
        token_id = token_hex(16)
        refresh_family_id = family_id or token_hex(16)
        refresh_session = RefreshTokenSession(
            user_id=user.id,
            token_id=token_id,
            family_id=refresh_family_id,
            token_hash="pending",
            issued_at=now,
            expires_at=now + timedelta(days=settings.refresh_token_expire_days),
            last_activity_at=now,
            user_agent=user_agent[:500] if user_agent else None,
            source_ip=source_ip,
        )
        refresh_session = await self.refresh_repository.create(refresh_session)
        access_token = create_access_token(user, session_id=refresh_session.id)
        refresh_token = create_refresh_token(
            user,
            token_id=token_id,
            family_id=refresh_family_id,
            session_id=refresh_session.id,
        )
        refresh_session.token_hash = self._hash_token(refresh_token)
        await self.repository.session.commit()
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserRead.model_validate(user),
        )

    @staticmethod
    def _hash_token(token: str) -> str:
        return sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=UTC)
