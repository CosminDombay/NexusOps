from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.ssh import ParamikoSshAdapter
from backend.app.db.session import get_db_session
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.jobs.repository import JobRepository
from backend.app.modules.jobs.schemas import BulkExecutionRead, JobRead
from backend.app.modules.jobs.service import JobService, JobTargetNotFoundError, JobTargetNotManagedError
from backend.app.modules.packages.repository import PackageDefinitionRepository
from backend.app.modules.packages.schemas import PackageDefinitionRead
from backend.app.modules.packages.schemas import (
    PackageDefinitionCreate,
    PackageDefinitionUpdate,
    PackageBulkApplyRequest,
    PackageExecuteRequest,
)
from backend.app.modules.packages.service import (
    BuiltinPackageDefinitionError,
    PackageAutomationService,
    PackageDefinitionConflictError,
    PackageDefinitionNotFoundError,
)

router = APIRouter()


async def get_package_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PackageAutomationService:
    return PackageAutomationService(
        repository=PackageDefinitionRepository(session),
        job_service=JobService(
            job_repository=JobRepository(session),
            server_repository=ServerRepository(session),
            ssh_adapter=ParamikoSshAdapter(),
        ),
    )


@router.get("", response_model=list[PackageDefinitionRead])
async def list_package_definitions(
    service: Annotated[PackageAutomationService, Depends(get_package_service)],
) -> list[PackageDefinitionRead]:
    return await service.list_definitions()


@router.post("/apply/bulk", response_model=BulkExecutionRead, status_code=status.HTTP_201_CREATED)
async def execute_package_bulk(
    payload: PackageBulkApplyRequest,
    service: Annotated[PackageAutomationService, Depends(get_package_service)],
) -> BulkExecutionRead:
    try:
        return await service.execute_definition_bulk(payload)
    except PackageDefinitionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("", response_model=PackageDefinitionRead, status_code=status.HTTP_201_CREATED)
async def create_package_definition(
    payload: PackageDefinitionCreate,
    service: Annotated[PackageAutomationService, Depends(get_package_service)],
) -> PackageDefinitionRead:
    try:
        return await service.create_definition(payload)
    except PackageDefinitionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/{package_id}", response_model=PackageDefinitionRead)
async def get_package_definition(
    package_id: str,
    service: Annotated[PackageAutomationService, Depends(get_package_service)],
) -> PackageDefinitionRead:
    try:
        return await service.get_definition(package_id)
    except PackageDefinitionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/{package_id}", response_model=PackageDefinitionRead)
async def update_package_definition(
    package_id: str,
    payload: PackageDefinitionUpdate,
    service: Annotated[PackageAutomationService, Depends(get_package_service)],
) -> PackageDefinitionRead:
    try:
        return await service.update_definition(package_id, payload)
    except PackageDefinitionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except BuiltinPackageDefinitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_package_definition(
    package_id: str,
    service: Annotated[PackageAutomationService, Depends(get_package_service)],
) -> None:
    try:
        await service.delete_definition(package_id)
    except PackageDefinitionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except BuiltinPackageDefinitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{package_id}/execute", response_model=JobRead, status_code=status.HTTP_201_CREATED)
async def execute_package_definition(
    package_id: str,
    payload: PackageExecuteRequest,
    service: Annotated[PackageAutomationService, Depends(get_package_service)],
) -> JobRead:
    try:
        return await service.execute_definition(package_id, payload)
    except PackageDefinitionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobTargetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobTargetNotManagedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except JobTargetNotManagedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
