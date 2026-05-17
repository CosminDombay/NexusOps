from uuid import UUID

from sqlalchemy import or_, select

from backend.app.common.repository import BaseRepository
from backend.app.modules.auth.models import User


class UserRepository(BaseRepository[User]):
    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

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
