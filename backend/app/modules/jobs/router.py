from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.ssh import ParamikoSshAdapter
from backend.app.db.session import get_db_session
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.jobs.repository import JobRepository
from backend.app.modules.jobs.schemas import (
    JobActionExecuteRequest,
    JobExecuteRequest,
    JobRead,
    OperationalActionRead,
)
from backend.app.modules.jobs.service import (
    JobNotFoundError,
    JobService,
    JobTargetNotFoundError,
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
    except OperationalActionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


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


@router.post("/{job_id}/cancel", response_model=JobRead)
async def cancel_job(
    job_id: UUID,
    service: Annotated[JobService, Depends(get_job_service)],
) -> JobRead:
    try:
        return await service.cancel_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
