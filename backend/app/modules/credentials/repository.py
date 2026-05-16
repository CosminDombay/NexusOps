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

    async def get_by_id(self, credential_id: UUID) -> Credential | None:
        result = await self.session.execute(select(Credential).where(Credential.id == credential_id))
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Credential | None:
        result = await self.session.execute(select(Credential).where(Credential.name == name))
        return result.scalar_one_or_none()

    async def list(self) -> list[Credential]:
        result = await self.session.execute(select(Credential).order_by(Credential.created_at.desc()))
        return list(result.scalars().all())

    async def delete(self, credential: Credential) -> None:
        await self.session.delete(credential)
