from backend.app.common.repository import BaseRepository
from backend.app.modules.packages.models import PackageDefinitionRecord, PackageInstallation

from sqlalchemy import delete, select
from uuid import UUID


class PackageInstallationRepository(BaseRepository[PackageInstallation]):
    pass


class PackageDefinitionRepository(BaseRepository[PackageDefinitionRecord]):
    async def create(self, definition: PackageDefinitionRecord) -> PackageDefinitionRecord:
        self.session.add(definition)
        await self.session.flush()
        await self.session.refresh(definition)
        return definition

    async def list(self) -> list[PackageDefinitionRecord]:
        result = await self.session.execute(
            select(PackageDefinitionRecord).order_by(PackageDefinitionRecord.name.asc())
        )
        return list(result.scalars().all())

    async def get_by_slug(self, slug: str) -> PackageDefinitionRecord | None:
        result = await self.session.execute(
            select(PackageDefinitionRecord).where(PackageDefinitionRecord.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, definition_id: UUID) -> PackageDefinitionRecord | None:
        result = await self.session.execute(
            select(PackageDefinitionRecord).where(PackageDefinitionRecord.id == definition_id)
        )
        return result.scalar_one_or_none()

    async def delete(self, definition: PackageDefinitionRecord) -> None:
        await self.session.execute(
            delete(PackageDefinitionRecord).where(PackageDefinitionRecord.id == definition.id)
        )
