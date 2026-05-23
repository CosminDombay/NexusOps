from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db_session
from backend.app.modules.audit.schemas import AuditEventRead
from backend.app.modules.audit.service import audit_service_from_session

router = APIRouter()


@router.get("", response_model=list[AuditEventRead])
async def list_audit_events(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    event_type: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    actor_user_id: UUID | None = None,
    workflow_run_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[AuditEventRead]:
    return await audit_service_from_session(session).list_events(
        event_type=event_type,
        target_type=target_type,
        target_id=target_id,
        actor_user_id=actor_user_id,
        workflow_run_id=workflow_run_id,
        limit=limit,
    )
