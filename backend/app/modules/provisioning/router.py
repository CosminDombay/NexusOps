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
from backend.app.modules.provisioning.repository import ProvisioningRequestRepository
from backend.app.modules.provisioning.schemas import (
    ProxmoxTemplateRead,
    ProvisioningCreate,
    ProvisioningRead,
)
from backend.app.modules.provisioning.service import (
    ProvisioningNotFoundError,
    ProvisioningService,
)

router = APIRouter()


async def get_provisioning_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProvisioningService:
    return ProvisioningService(
        repository=ProvisioningRequestRepository(session),
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
