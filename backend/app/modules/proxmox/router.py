from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.proxmox import (
    ProxmoxConfigurationError,
    ProxmoxConnectionError,
)
from backend.app.db.session import get_db_session
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.integrations.repository import IntegrationRepository
from backend.app.modules.integrations.service import IntegrationService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.proxmox.schemas import (
    ProxmoxClusterSummaryRead,
    ProxmoxDashboardRead,
    ProxmoxNodeRead,
    ProxmoxNodeDetailRead,
    ProxmoxStorageRead,
    ProxmoxVmActionRead,
    ProxmoxVmRead,
)
from backend.app.modules.proxmox.service import (
    ProxmoxService,
    ProxmoxVmActionNotAllowedError,
    ProxmoxVmNotFoundError,
)

router = APIRouter()


async def get_proxmox_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProxmoxService:
    integration_service = IntegrationService(
        IntegrationRepository(session),
        credential_service=CredentialService(repository=CredentialRepository(session)),
    )
    return ProxmoxService(
        await integration_service.get_proxmox_adapter(),
        server_repository=ServerRepository(session),
    )


def _map_proxmox_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ProxmoxVmNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ProxmoxVmActionNotAllowedError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, ProxmoxConfigurationError):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    if isinstance(exc, ProxmoxConnectionError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="Unable to read Proxmox infrastructure state",
    )


@router.get("/nodes", response_model=list[ProxmoxNodeRead])
async def get_nodes(
    service: Annotated[ProxmoxService, Depends(get_proxmox_service)],
) -> list[ProxmoxNodeRead]:
    try:
        return await service.get_nodes()
    except (ProxmoxConfigurationError, ProxmoxConnectionError) as exc:
        raise _map_proxmox_error(exc) from exc


@router.get("/nodes/{node_name}", response_model=ProxmoxNodeDetailRead)
async def get_node_detail(
    node_name: str,
    service: Annotated[ProxmoxService, Depends(get_proxmox_service)],
) -> ProxmoxNodeDetailRead:
    try:
        return await service.get_node_detail(node_name)
    except (ProxmoxConfigurationError, ProxmoxConnectionError, ProxmoxVmNotFoundError) as exc:
        raise _map_proxmox_error(exc) from exc


@router.get("/vms", response_model=list[ProxmoxVmRead])
async def list_vms(
    service: Annotated[ProxmoxService, Depends(get_proxmox_service)],
) -> list[ProxmoxVmRead]:
    try:
        return await service.list_vms()
    except (ProxmoxConfigurationError, ProxmoxConnectionError) as exc:
        raise _map_proxmox_error(exc) from exc


@router.get("/storage", response_model=list[ProxmoxStorageRead])
async def list_storage(
    service: Annotated[ProxmoxService, Depends(get_proxmox_service)],
    node_name: str | None = None,
) -> list[ProxmoxStorageRead]:
    try:
        return await service.list_storage(node_name)
    except (ProxmoxConfigurationError, ProxmoxConnectionError) as exc:
        raise _map_proxmox_error(exc) from exc


@router.get("/vms/{node}/{vm_type}/{vm_id}/status", response_model=ProxmoxVmRead)
async def get_vm_status(
    node: str,
    vm_type: str,
    vm_id: int,
    service: Annotated[ProxmoxService, Depends(get_proxmox_service)],
) -> ProxmoxVmRead:
    try:
        return await service.get_vm_status(node=node, vm_id=vm_id, vm_type=vm_type)
    except (ProxmoxConfigurationError, ProxmoxConnectionError) as exc:
        raise _map_proxmox_error(exc) from exc


@router.get("/cluster/summary", response_model=ProxmoxClusterSummaryRead)
async def get_cluster_summary(
    service: Annotated[ProxmoxService, Depends(get_proxmox_service)],
) -> ProxmoxClusterSummaryRead:
    try:
        return await service.get_cluster_summary()
    except (ProxmoxConfigurationError, ProxmoxConnectionError) as exc:
        raise _map_proxmox_error(exc) from exc


@router.get("/dashboard", response_model=ProxmoxDashboardRead)
async def get_dashboard(
    service: Annotated[ProxmoxService, Depends(get_proxmox_service)],
) -> ProxmoxDashboardRead:
    try:
        return await service.get_dashboard()
    except (ProxmoxConfigurationError, ProxmoxConnectionError) as exc:
        raise _map_proxmox_error(exc) from exc


@router.post("/vms/{vm_id}/start", response_model=ProxmoxVmActionRead)
async def start_vm(
    vm_id: int,
    service: Annotated[ProxmoxService, Depends(get_proxmox_service)],
) -> ProxmoxVmActionRead:
    try:
        return await service.start_vm(vm_id)
    except (
        ProxmoxConfigurationError,
        ProxmoxConnectionError,
        ProxmoxVmActionNotAllowedError,
        ProxmoxVmNotFoundError,
    ) as exc:
        raise _map_proxmox_error(exc) from exc


@router.post("/vms/{vm_id}/stop", response_model=ProxmoxVmActionRead)
async def stop_vm(
    vm_id: int,
    service: Annotated[ProxmoxService, Depends(get_proxmox_service)],
) -> ProxmoxVmActionRead:
    try:
        return await service.stop_vm(vm_id)
    except (
        ProxmoxConfigurationError,
        ProxmoxConnectionError,
        ProxmoxVmActionNotAllowedError,
        ProxmoxVmNotFoundError,
    ) as exc:
        raise _map_proxmox_error(exc) from exc


@router.post("/vms/{vm_id}/reboot", response_model=ProxmoxVmActionRead)
async def reboot_vm(
    vm_id: int,
    service: Annotated[ProxmoxService, Depends(get_proxmox_service)],
) -> ProxmoxVmActionRead:
    try:
        return await service.reboot_vm(vm_id)
    except (
        ProxmoxConfigurationError,
        ProxmoxConnectionError,
        ProxmoxVmActionNotAllowedError,
        ProxmoxVmNotFoundError,
    ) as exc:
        raise _map_proxmox_error(exc) from exc


@router.post("/vms/{vm_id}/shutdown", response_model=ProxmoxVmActionRead)
async def shutdown_vm(
    vm_id: int,
    service: Annotated[ProxmoxService, Depends(get_proxmox_service)],
) -> ProxmoxVmActionRead:
    try:
        return await service.shutdown_vm(vm_id)
    except (
        ProxmoxConfigurationError,
        ProxmoxConnectionError,
        ProxmoxVmActionNotAllowedError,
        ProxmoxVmNotFoundError,
    ) as exc:
        raise _map_proxmox_error(exc) from exc
