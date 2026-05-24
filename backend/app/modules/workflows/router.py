from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db_session
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.workflows.repository import WorkflowRunRepository, WorkflowStepRepository
from backend.app.modules.workflows.schemas import WorkflowRunRead
from backend.app.modules.workflows.service import WorkflowNotFoundError, WorkflowService

router = APIRouter()


async def get_workflow_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> WorkflowService:
    return WorkflowService(
        workflow_repository=WorkflowRunRepository(session),
        step_repository=WorkflowStepRepository(session),
        server_repository=ServerRepository(session),
    )


@router.get("", response_model=list[WorkflowRunRead])
async def list_workflows(
    service: Annotated[WorkflowService, Depends(get_workflow_service)],
    target_server_id: UUID | None = None,
) -> list[WorkflowRunRead]:
    return await service.list_workflows(target_server_id=target_server_id)


@router.get("/{workflow_run_id}", response_model=WorkflowRunRead)
async def get_workflow(
    workflow_run_id: UUID,
    service: Annotated[WorkflowService, Depends(get_workflow_service)],
) -> WorkflowRunRead:
    try:
        return await service.get_workflow(workflow_run_id)
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
