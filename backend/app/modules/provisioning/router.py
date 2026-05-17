from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.proxmox import HttpProxmoxAdapter, ProxmoxConfigurationError, ProxmoxConnectionError
from backend.app.adapters.ssh import ParamikoSshAdapter
from backend.app.db.session import get_db_session
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.jobs.repository import JobRepository
from backend.app.modules.packages.repository import PackageDefinitionRepository
from backend.app.modules.profiles.repository import InfrastructureProfileRepository
from backend.app.modules.provisioning.repository import (
    ProvisioningBlueprintRepository,
    ProvisioningRequestRepository,
)
from backend.app.modules.provisioning.schemas import (
    ProxmoxTemplateRead,
    ProvisioningBlueprintCreate,
    ProvisioningBlueprintRead,
    ProvisioningBlueprintUpdate,
    ProvisioningCreate,
    ProvisioningRead,
)
from backend.app.modules.provisioning.service import (
    ProvisioningBlueprintConflictError,
    ProvisioningBlueprintNotFoundError,
    ProvisioningNotFoundError,
    ProvisioningService,
)

router = APIRouter()


async def get_provisioning_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProvisioningService:
    return ProvisioningService(
        repository=ProvisioningRequestRepository(session),
        blueprint_repository=ProvisioningBlueprintRepository(session),
        server_repository=ServerRepository(session),
        job_repository=JobRepository(session),
        package_repository=PackageDefinitionRepository(session),
        profile_repository=InfrastructureProfileRepository(session),
        proxmox_adapter=HttpProxmoxAdapter(),
        ssh_adapter=ParamikoSshAdapter(),
    )


def _map_provider_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ProxmoxConfigurationError):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    if isinstance(exc, ProxmoxConnectionError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("", response_model=list[ProvisioningRead])
async def list_provisioning_requests(
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
) -> list[ProvisioningRead]:
    return await service.list_requests()


@router.get("/templates", response_model=list[ProxmoxTemplateRead])
async def list_templates(
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
) -> list[ProxmoxTemplateRead]:
    try:
        return await service.list_templates()
    except (ProxmoxConfigurationError, ProxmoxConnectionError) as exc:
        raise _map_provider_error(exc) from exc


@router.get("/blueprints", response_model=list[ProvisioningBlueprintRead])
async def list_blueprints(
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
) -> list[ProvisioningBlueprintRead]:
    return await service.list_blueprints()


@router.post("/blueprints", response_model=ProvisioningBlueprintRead, status_code=status.HTTP_201_CREATED)
async def create_blueprint(
    payload: ProvisioningBlueprintCreate,
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
) -> ProvisioningBlueprintRead:
    try:
        return await service.create_blueprint(payload)
    except ProvisioningBlueprintConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.put("/blueprints/{blueprint_id}", response_model=ProvisioningBlueprintRead)
async def update_blueprint(
    blueprint_id: UUID,
    payload: ProvisioningBlueprintUpdate,
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
) -> ProvisioningBlueprintRead:
    try:
        return await service.update_blueprint(blueprint_id, payload)
    except ProvisioningBlueprintNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProvisioningBlueprintConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/blueprints/{blueprint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_blueprint(
    blueprint_id: UUID,
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
) -> None:
    try:
        await service.delete_blueprint(blueprint_id)
    except ProvisioningBlueprintNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{request_id}", response_model=ProvisioningRead)
async def get_provisioning_request(
    request_id: UUID,
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
) -> ProvisioningRead:
    try:
        return await service.get_request(request_id)
    except ProvisioningNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("", response_model=ProvisioningRead, status_code=status.HTTP_201_CREATED)
async def provision_vm(
    payload: ProvisioningCreate,
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
) -> ProvisioningRead:
    try:
        return await service.provision(payload)
    except (ProxmoxConfigurationError, ProxmoxConnectionError) as exc:
        raise _map_provider_error(exc) from exc
