from datetime import UTC, datetime
from uuid import UUID

import structlog
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.audit.models import AuditEvent
from backend.app.modules.audit.repository import AuditEventRepository
from backend.app.modules.audit.schemas import AuditEventRead
from backend.app.modules.auth.models import User

logger = structlog.get_logger(__name__)


class AuditService:
    def __init__(self, repository: AuditEventRepository) -> None:
        self.repository = repository

    async def record(
        self,
        *,
        event_type: str,
        actor: User | None = None,
        actor_user_id: UUID | None = None,
        actor_username: str | None = None,
        target_type: str | None = None,
        target_id: UUID | str | None = None,
        result: str = "success",
        metadata: dict[str, object] | None = None,
        source_ip: str | None = None,
        correlation_id: str | None = None,
        workflow_run_id: UUID | None = None,
        error: str | None = None,
        commit: bool = True,
    ) -> AuditEvent | None:
        event = AuditEvent(
            event_type=event_type,
            actor_user_id=actor.id if actor and actor.id else actor_user_id,
            actor_username=actor.username if actor else actor_username,
            occurred_at=datetime.now(UTC),
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            result=result,
            metadata_json=metadata or {},
            source_ip=source_ip,
            correlation_id=correlation_id,
            workflow_run_id=workflow_run_id,
            error=error,
        )
        try:
            async with self.repository.session.begin_nested():
                created = await self.repository.create(event)
            if commit:
                await self.repository.session.commit()
            logger.info(
                "audit_event_recorded",
                event_type=event_type,
                result=result,
                target_type=target_type,
                target_id=str(target_id) if target_id is not None else None,
            )
            return created
        except Exception as exc:
            if commit:
                await self.repository.session.rollback()
            logger.warning("audit_event_persist_failed", event_type=event_type, reason=str(exc))
            return None

    async def list_events(
        self,
        *,
        event_type: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        actor_user_id: UUID | None = None,
        workflow_run_id: UUID | None = None,
        limit: int = 100,
    ) -> list[AuditEventRead]:
        events = await self.repository.list(
            event_type=event_type,
            target_type=target_type,
            target_id=target_id,
            actor_user_id=actor_user_id,
            workflow_run_id=workflow_run_id,
            limit=limit,
        )
        return [AuditEventRead.model_validate(event) for event in events]


def source_ip_from_request(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host


def audit_service_from_session(session: AsyncSession) -> AuditService:
    return AuditService(AuditEventRepository(session))
