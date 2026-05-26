from uuid import UUID

from sqlalchemy import or_, select

from backend.app.common.repository import BaseRepository
from backend.app.modules.auth.models import RefreshTokenSession, RemoteAccessToken, User


class UserRepository(BaseRepository[User]):
    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def list(self) -> list[User]:
        result = await self.session.execute(select(User).order_by(User.created_at.desc()))
        return list(result.scalars().all())

    async def get_by_username(self, username: str) -> User | None:
        result = await self.session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_login(self, login: str) -> User | None:
        normalized = login.strip().lower()
        result = await self.session.execute(
            select(User).where(
                or_(User.email == normalized, User.username == normalized),
            )
        )
        return result.scalar_one_or_none()

    async def exists_by_username_or_email(self, username: str, email: str) -> bool:
        result = await self.session.execute(
            select(User.id).where(or_(User.username == username, User.email == email))
        )
        return result.scalar_one_or_none() is not None


class RefreshTokenSessionRepository(BaseRepository[RefreshTokenSession]):
    async def create(self, session: RefreshTokenSession) -> RefreshTokenSession:
        self.session.add(session)
        await self.session.flush()
        await self.session.refresh(session)
        return session

    async def get_by_id(self, session_id: UUID) -> RefreshTokenSession | None:
        result = await self.session.execute(select(RefreshTokenSession).where(RefreshTokenSession.id == session_id))
        return result.scalar_one_or_none()

    async def get_by_token_id(self, token_id: str) -> RefreshTokenSession | None:
        result = await self.session.execute(select(RefreshTokenSession).where(RefreshTokenSession.token_id == token_id))
        return result.scalar_one_or_none()

    async def list_active_for_user(self, user_id: UUID) -> list[RefreshTokenSession]:
        result = await self.session.execute(
            select(RefreshTokenSession).where(
                RefreshTokenSession.user_id == user_id,
                RefreshTokenSession.revoked_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def list_family(self, user_id: UUID, family_id: str) -> list[RefreshTokenSession]:
        result = await self.session.execute(
            select(RefreshTokenSession).where(
                RefreshTokenSession.user_id == user_id,
                RefreshTokenSession.family_id == family_id,
            )
        )
        return list(result.scalars().all())


class RemoteAccessTokenRepository(BaseRepository[RemoteAccessToken]):
    async def create(self, token: RemoteAccessToken) -> RemoteAccessToken:
        self.session.add(token)
        await self.session.flush()
        await self.session.refresh(token)
        return token

    async def get_by_token_id(self, token_id: str) -> RemoteAccessToken | None:
        result = await self.session.execute(select(RemoteAccessToken).where(RemoteAccessToken.token_id == token_id))
        return result.scalar_one_or_none()
