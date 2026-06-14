from uuid import UUID

from sqlalchemy import select

from backend.app.common.repository import BaseRepository
from backend.app.modules.credentials.models import Credential


class CredentialRepository(BaseRepository[Credential]):
    async def create(self, credential: Credential) -> Credential:
        self.session.add(credential)
        await self.session.flush()
        await self.session.refresh(credential)
        return credential

    async def get_by_id(self, credential_id: UUID, *, include_deleted: bool = False) -> Credential | None:
        query = select(Credential).where(Credential.id == credential_id)
        if not include_deleted:
            query = query.where(Credential.deleted_at.is_(None))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str, *, include_deleted: bool = False) -> Credential | None:
        query = select(Credential).where(Credential.name == name)
        if not include_deleted:
            query = query.where(Credential.deleted_at.is_(None))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list(self, *, include_deleted: bool = False, only_deleted: bool = False) -> list[Credential]:
        query = select(Credential)
        if only_deleted:
            query = query.where(Credential.deleted_at.is_not(None))
        elif not include_deleted:
            query = query.where(Credential.deleted_at.is_(None))
        result = await self.session.execute(query.order_by(Credential.created_at.desc()))
        return list(result.scalars().all())

    async def delete(self, credential: Credential) -> None:
        await self.session.delete(credential)
