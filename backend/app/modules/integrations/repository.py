from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from backend.app.common.repository import BaseRepository
from backend.app.modules.integrations.models import Integration, IntegrationProviderType, IntegrationType


class IntegrationRepository(BaseRepository[Integration]):
    async def create(self, integration: Integration) -> Integration:
        self.session.add(integration)
        await self.session.flush()
        await self.session.refresh(integration)
        return integration

    async def get_by_id(self, integration_id: UUID, *, include_deleted: bool = False) -> Integration | None:
        query = select(Integration).where(Integration.id == integration_id)
        if not include_deleted:
            query = query.where(Integration.deleted_at.is_(None))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def delete(self, integration: Integration) -> None:
        await self.session.delete(integration)
        await self.session.flush()

    async def list(self, *, include_deleted: bool = False, only_deleted: bool = False) -> list[Integration]:
        query = select(Integration)
        if only_deleted:
            query = query.where(Integration.deleted_at.is_not(None))
        elif not include_deleted:
            query = query.where(Integration.deleted_at.is_(None))
        result = await self.session.execute(query.order_by(Integration.name.asc()))
        return list(result.scalars().all())

    async def list_enabled_by_type(self, integration_type: IntegrationType) -> list[Integration]:
        result = await self.session.execute(
            select(Integration)
            .where(Integration.enabled.is_(True), Integration.type == integration_type)
            .where(Integration.deleted_at.is_(None))
            .order_by(Integration.name.asc())
        )
        return list(result.scalars().all())

    async def list_by_type(self, integration_type: IntegrationType) -> list[Integration]:
        result = await self.session.execute(
            select(Integration)
            .where(Integration.type == integration_type)
            .where(Integration.deleted_at.is_(None))
            .order_by(Integration.name.asc())
        )
        return list(result.scalars().all())

    async def list_enabled_by_provider(self, provider_type: IntegrationProviderType) -> list[Integration]:
        result = await self.session.execute(
            select(Integration)
            .where(Integration.enabled.is_(True), Integration.provider_type == provider_type)
            .where(Integration.deleted_at.is_(None))
            .order_by(Integration.name.asc())
        )
        return list(result.scalars().all())

    async def list_by_provider(self, provider_type: IntegrationProviderType) -> list[Integration]:
        result = await self.session.execute(
            select(Integration)
            .where(Integration.provider_type == provider_type)
            .where(Integration.deleted_at.is_(None))
            .order_by(Integration.name.asc())
        )
        return list(result.scalars().all())
