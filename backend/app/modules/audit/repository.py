from uuid import UUID

from sqlalchemy import select

from backend.app.common.repository import BaseRepository
from backend.app.modules.audit.models import AuditEvent


class AuditEventRepository(BaseRepository[AuditEvent]):
    async def create(self, event: AuditEvent) -> AuditEvent:
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def list(
        self,
        *,
        event_type: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        actor_user_id: UUID | None = None,
        workflow_run_id: UUID | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        query = select(AuditEvent).order_by(AuditEvent.occurred_at.desc()).limit(limit)
        if event_type:
            query = query.where(AuditEvent.event_type == event_type)
        if target_type:
            query = query.where(AuditEvent.target_type == target_type)
        if target_id:
            query = query.where(AuditEvent.target_id == target_id)
        if actor_user_id:
            query = query.where(AuditEvent.actor_user_id == actor_user_id)
        if workflow_run_id:
            query = query.where(AuditEvent.workflow_run_id == workflow_run_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())
