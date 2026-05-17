from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from backend.app.common.repository import BaseRepository
from backend.app.modules.integrations.models import Integration, IntegrationType


class IntegrationRepository(BaseRepository[Integration]):
    async def create(self, integration: Integration) -> Integration:
        self.session.add(integration)
        await self.session.flush()
        await self.session.refresh(integration)
        return integration

    async def get_by_id(self, integration_id: UUID) -> Integration | None:
        result = await self.session.execute(select(Integration).where(Integration.id == integration_id))
        return result.scalar_one_or_none()

    async def list(self) -> list[Integration]:
        result = await self.session.execute(select(Integration).order_by(Integration.name.asc()))
        return list(result.scalars().all())

    async def list_enabled_by_type(self, integration_type: IntegrationType) -> list[Integration]:
        result = await self.session.execute(
            select(Integration)
            .where(Integration.enabled.is_(True), Integration.type == integration_type)
            .order_by(Integration.name.asc())
        )
        return list(result.scalars().all())
