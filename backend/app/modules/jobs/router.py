from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.ssh import ParamikoSshAdapter
from backend.app.db.session import get_db_session
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.jobs.repository import JobRepository
from backend.app.modules.jobs.repository import CustomOperationalActionRepository
from backend.app.modules.jobs.schemas import (
    BulkExecutionRead,
    JobActionExecuteRequest,
    JobBulkExecuteRequest,
    JobExecuteRequest,
    JobRead,
    OperationalActionCreate,
    OperationalActionRead,
    OperationalActionUpdate,
)
from backend.app.modules.jobs.service import (
    BuiltinOperationalActionError,
    JobNotFoundError,
    JobService,
    JobTargetNotFoundError,
    JobTargetNotManagedError,
    OperationalActionConflictError,
    OperationalActionNotFoundError,
)

router = APIRouter()


async def get_job_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> JobService:
    return JobService(
        job_repository=JobRepository(session),
        server_repository=ServerRepository(session),
        ssh_adapter=ParamikoSshAdapter(),
        action_repository=CustomOperationalActionRepository(session),
        credential_service=CredentialService(repository=CredentialRepository(session)),
    )


@router.get("", response_model=list[JobRead])
async def list_jobs(
    service: Annotated[JobService, Depends(get_job_service)],
) -> list[JobRead]:
    return await service.list_jobs()


@router.get("/actions", response_model=list[OperationalActionRead])
async def list_actions(
    service: Annotated[JobService, Depends(get_job_service)],
) -> list[OperationalActionRead]:
    return await service.list_actions()


@router.post("/actions/execute", response_model=JobRead, status_code=status.HTTP_201_CREATED)
async def execute_action(
    payload: JobActionExecuteRequest,
    service: Annotated[JobService, Depends(get_job_service)],
) -> JobRead:
    try:
        return await service.execute_action(payload)
    except JobTargetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobTargetNotManagedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except OperationalActionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/actions", response_model=OperationalActionRead, status_code=status.HTTP_201_CREATED)
async def create_action(
    payload: OperationalActionCreate,
    service: Annotated[JobService, Depends(get_job_service)],
) -> OperationalActionRead:
    try:
        return await service.create_action(payload)
    except OperationalActionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.put("/actions/{action_id}", response_model=OperationalActionRead)
async def update_action(
    action_id: str,
    payload: OperationalActionUpdate,
    service: Annotated[JobService, Depends(get_job_service)],
) -> OperationalActionRead:
    try:
        return await service.update_action(action_id, payload)
    except BuiltinOperationalActionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except OperationalActionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/actions/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_action(
    action_id: str,
    service: Annotated[JobService, Depends(get_job_service)],
) -> None:
    try:
        await service.delete_action(action_id)
    except BuiltinOperationalActionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except OperationalActionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/execute/bulk", response_model=BulkExecutionRead, status_code=status.HTTP_201_CREATED)
async def execute_job_bulk(
    payload: JobBulkExecuteRequest,
    service: Annotated[JobService, Depends(get_job_service)],
) -> BulkExecutionRead:
    return await service.execute_bulk(payload)


@router.get("/{job_id}", response_model=JobRead)
async def get_job(
    job_id: UUID,
    service: Annotated[JobService, Depends(get_job_service)],
) -> JobRead:
    try:
        return await service.get_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/execute", response_model=JobRead, status_code=status.HTTP_201_CREATED)
async def execute_job(
    payload: JobExecuteRequest,
    service: Annotated[JobService, Depends(get_job_service)],
) -> JobRead:
    try:
        return await service.execute(payload)
    except JobTargetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobTargetNotManagedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{job_id}/cancel", response_model=JobRead)
async def cancel_job(
    job_id: UUID,
    service: Annotated[JobService, Depends(get_job_service)],
) -> JobRead:
    try:
        return await service.cancel_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
