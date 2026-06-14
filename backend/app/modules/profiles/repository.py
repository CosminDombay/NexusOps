from backend.app.common.repository import BaseRepository
from backend.app.modules.profiles.models import InfrastructureProfileRecord, StandardizationProfile

from sqlalchemy import delete, select
from uuid import UUID


class StandardizationProfileRepository(BaseRepository[StandardizationProfile]):
    pass


class InfrastructureProfileRepository(BaseRepository[InfrastructureProfileRecord]):
    async def create(self, profile: InfrastructureProfileRecord) -> InfrastructureProfileRecord:
        self.session.add(profile)
        await self.session.flush()
        await self.session.refresh(profile)
        return profile

    async def list(
        self,
        *,
        include_deleted: bool = False,
        only_deleted: bool = False,
    ) -> list[InfrastructureProfileRecord]:
        query = select(InfrastructureProfileRecord)
        if only_deleted:
            query = query.where(InfrastructureProfileRecord.deleted_at.is_not(None))
        elif not include_deleted:
            query = query.where(InfrastructureProfileRecord.deleted_at.is_(None))
        result = await self.session.execute(query.order_by(InfrastructureProfileRecord.name.asc()))
        return list(result.scalars().all())

    async def get_by_slug(self, slug: str, *, include_deleted: bool = False) -> InfrastructureProfileRecord | None:
        query = select(InfrastructureProfileRecord).where(InfrastructureProfileRecord.slug == slug)
        if not include_deleted:
            query = query.where(InfrastructureProfileRecord.deleted_at.is_(None))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id(self, profile_id: UUID, *, include_deleted: bool = False) -> InfrastructureProfileRecord | None:
        query = select(InfrastructureProfileRecord).where(InfrastructureProfileRecord.id == profile_id)
        if not include_deleted:
            query = query.where(InfrastructureProfileRecord.deleted_at.is_(None))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def delete(self, profile: InfrastructureProfileRecord) -> None:
        await self.session.execute(
            delete(InfrastructureProfileRecord).where(InfrastructureProfileRecord.id == profile.id)
        )
