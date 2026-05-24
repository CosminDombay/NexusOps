from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from backend.app.common.repository import BaseRepository
from backend.app.modules.automations.models import Automation


class AutomationRepository(BaseRepository[Automation]):
    async def create(self, automation: Automation) -> Automation:
        self.session.add(automation)
        await self.session.flush()
        await self.session.refresh(automation)
        return automation

    async def get_by_id(self, automation_id: UUID) -> Automation | None:
        result = await self.session.execute(select(Automation).where(Automation.id == automation_id))
        return result.scalar_one_or_none()

    async def list(self) -> list[Automation]:
        result = await self.session.execute(select(Automation).order_by(Automation.created_at.desc()))
        return list(result.scalars().all())

    async def list_for_target(self, target_server_id: UUID) -> list[Automation]:
        automations = await self.list()
        return [
            automation
            for automation in automations
            if str(target_server_id) in {str(item) for item in automation.target_server_ids}
        ]

    async def list_enabled(self) -> list[Automation]:
        result = await self.session.execute(
            select(Automation).where(Automation.enabled.is_(True)).order_by(Automation.name.asc())
        )
        return list(result.scalars().all())

    async def delete(self, automation: Automation) -> None:
        await self.session.delete(automation)
