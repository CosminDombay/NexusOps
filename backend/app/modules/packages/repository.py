from uuid import UUID

from sqlalchemy import delete, select

from backend.app.common.repository import BaseRepository
from backend.app.modules.packages.models import PackageDefinitionRecord, PackageInstallation


class PackageInstallationRepository(BaseRepository[PackageInstallation]):
    pass


class PackageDefinitionRepository(BaseRepository[PackageDefinitionRecord]):
    async def create(self, definition: PackageDefinitionRecord) -> PackageDefinitionRecord:
        self.session.add(definition)
        await self.session.flush()
        await self.session.refresh(definition)
        return definition

    async def list(
        self,
        *,
        include_deleted: bool = False,
        only_deleted: bool = False,
    ) -> list[PackageDefinitionRecord]:
        query = select(PackageDefinitionRecord)
        if only_deleted:
            query = query.where(PackageDefinitionRecord.deleted_at.is_not(None))
        elif not include_deleted:
            query = query.where(PackageDefinitionRecord.deleted_at.is_(None))
        result = await self.session.execute(query.order_by(PackageDefinitionRecord.name.asc()))
        return list(result.scalars().all())

    async def get_by_slug(self, slug: str, *, include_deleted: bool = False) -> PackageDefinitionRecord | None:
        query = select(PackageDefinitionRecord).where(PackageDefinitionRecord.slug == slug)
        if not include_deleted:
            query = query.where(PackageDefinitionRecord.deleted_at.is_(None))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id(self, definition_id: UUID, *, include_deleted: bool = False) -> PackageDefinitionRecord | None:
        query = select(PackageDefinitionRecord).where(PackageDefinitionRecord.id == definition_id)
        if not include_deleted:
            query = query.where(PackageDefinitionRecord.deleted_at.is_(None))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def delete(self, definition: PackageDefinitionRecord) -> None:
        await self.session.execute(
            delete(PackageDefinitionRecord).where(PackageDefinitionRecord.id == definition.id)
        )
