from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db_session
from backend.app.modules.automations.factory import build_automation_service
from backend.app.modules.automations.schemas import AutomationCreate, AutomationRead, AutomationUpdate
from backend.app.modules.automations.service import AutomationNotFoundError, AutomationService, AutomationValidationError
from backend.app.modules.automations.tasks import execute_automation_workflow
from backend.app.modules.workflows.schemas import WorkflowRunRead
from backend.app.workers.queue.service import task_queue
from backend.app.workers.scheduler.service import scheduler_service

router = APIRouter()


async def get_automation_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AutomationService:
    return build_automation_service(session)


@router.get("", response_model=list[AutomationRead])
async def list_automations(
    service: Annotated[AutomationService, Depends(get_automation_service)],
    target_server_id: UUID | None = None,
) -> list[AutomationRead]:
    return await service.list_automations(target_server_id=target_server_id)


@router.post("", response_model=AutomationRead, status_code=status.HTTP_201_CREATED)
async def create_automation(
    payload: AutomationCreate,
    service: Annotated[AutomationService, Depends(get_automation_service)],
) -> AutomationRead:
    try:
        automation = await service.create_automation(payload)
        await scheduler_service.reload_automations()
        return automation
    except AutomationValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.put("/{automation_id}", response_model=AutomationRead)
async def update_automation(
    automation_id: UUID,
    payload: AutomationUpdate,
    service: Annotated[AutomationService, Depends(get_automation_service)],
) -> AutomationRead:
    try:
        automation = await service.update_automation(automation_id, payload)
        await scheduler_service.reload_automations()
        return automation
    except AutomationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AutomationValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.delete("/{automation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_automation(
    automation_id: UUID,
    service: Annotated[AutomationService, Depends(get_automation_service)],
) -> None:
    try:
        await service.delete_automation(automation_id)
        await scheduler_service.reload_automations()
    except AutomationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{automation_id}/enable", response_model=AutomationRead)
async def enable_automation(
    automation_id: UUID,
    service: Annotated[AutomationService, Depends(get_automation_service)],
) -> AutomationRead:
    try:
        automation = await service.enable_automation(automation_id)
        await scheduler_service.reload_automations()
        return automation
    except AutomationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{automation_id}/disable", response_model=AutomationRead)
async def disable_automation(
    automation_id: UUID,
    service: Annotated[AutomationService, Depends(get_automation_service)],
) -> AutomationRead:
    try:
        automation = await service.disable_automation(automation_id)
        await scheduler_service.reload_automations()
        return automation
    except AutomationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{automation_id}/run", response_model=WorkflowRunRead, status_code=status.HTTP_202_ACCEPTED)
async def run_automation(
    automation_id: UUID,
    service: Annotated[AutomationService, Depends(get_automation_service)],
) -> WorkflowRunRead:
    try:
        workflow = await service.create_run_workflow(automation_id)
        task_queue.submit(
            execute_automation_workflow(automation_id, workflow.id),
            name=f"automation:{automation_id}",
            owner="api",
            execution_origin="automation",
            correlation_id=str(workflow.id),
        )
        return workflow
    except AutomationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AutomationValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
