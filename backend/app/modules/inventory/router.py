from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.proxmox import ProxmoxConfigurationError, ProxmoxConnectionError
from backend.app.adapters.ssh import ParamikoSshAdapter
from backend.app.db.session import get_db_session
from backend.app.modules.auth.security.dependencies import require_operator
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.integrations.repository import IntegrationRepository
from backend.app.modules.integrations.service import IntegrationNotFoundError, IntegrationService
from backend.app.modules.inventory.discovery import HostDiscoveryError, HostDiscoveryService
from backend.app.modules.inventory.models import ServerEnvironment
from backend.app.modules.inventory.health import InventoryHealthService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.schemas import (
    HostDockerRead,
    HostNetworkRead,
    HostSystemRead,
    BulkInventoryHealthCheckRequest,
    InventoryHealthCheckResult,
    InventoryHealthSummary,
    ProxmoxInventoryImport,
    ServerCreate,
    ServerRead,
    ServerUpdate,
)
from backend.app.modules.inventory.service import (
    InventoryConflictError,
    InventoryService,
    ServerNotFoundError,
)
from backend.app.modules.proxmox.service import ProxmoxService

router = APIRouter()


async def get_inventory_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InventoryService:
    return InventoryService(ServerRepository(session))


async def get_inventory_health_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InventoryHealthService:
    return InventoryHealthService(ServerRepository(session))


async def get_host_discovery_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HostDiscoveryService:
    return HostDiscoveryService(
        ParamikoSshAdapter(),
        credential_service=CredentialService(repository=CredentialRepository(session)),
    )


@router.get("", response_model=list[ServerRead])
async def list_servers(
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    environment: ServerEnvironment | None = None,
    provider: str | None = None,
    integration_id: UUID | None = None,
    cluster: str | None = None,
    include_inactive: bool = False,
    search: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
) -> list[ServerRead]:
    return await service.list_servers(
        environment=environment,
        provider=provider,
        integration_id=integration_id,
        cluster=cluster,
        search=search,
        include_inactive=include_inactive,
    )


@router.post(
    "/health-check/bulk",
    response_model=list[InventoryHealthCheckResult],
    dependencies=[Depends(require_operator)],
)
async def bulk_health_check(
    payload: BulkInventoryHealthCheckRequest,
    service: Annotated[InventoryHealthService, Depends(get_inventory_health_service)],
) -> list[InventoryHealthCheckResult]:
    return await service.check_bulk(payload.server_ids)


@router.get("/health-summary", response_model=InventoryHealthSummary)
async def get_health_summary(
    service: Annotated[InventoryHealthService, Depends(get_inventory_health_service)],
) -> InventoryHealthSummary:
    return await service.summary()


@router.get("/{server_id}", response_model=ServerRead)
async def get_server(
    server_id: UUID,
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> ServerRead:
    try:
        return await service.get_server(server_id)
    except ServerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{server_id}/system",
    response_model=HostSystemRead,
    dependencies=[Depends(require_operator)],
)
async def get_server_system(
    server_id: UUID,
    inventory_service: Annotated[InventoryService, Depends(get_inventory_service)],
    discovery_service: Annotated[HostDiscoveryService, Depends(get_host_discovery_service)],
) -> HostSystemRead:
    try:
        server = await inventory_service.get_server(server_id)
        return await discovery_service.system(server)
    except ServerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except HostDiscoveryError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get(
    "/{server_id}/network",
    response_model=HostNetworkRead,
    dependencies=[Depends(require_operator)],
)
async def get_server_network(
    server_id: UUID,
    inventory_service: Annotated[InventoryService, Depends(get_inventory_service)],
    discovery_service: Annotated[HostDiscoveryService, Depends(get_host_discovery_service)],
) -> HostNetworkRead:
    try:
        server = await inventory_service.get_server(server_id)
        return await discovery_service.network(server)
    except ServerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except HostDiscoveryError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get(
    "/{server_id}/docker",
    response_model=HostDockerRead,
    dependencies=[Depends(require_operator)],
)
async def get_server_docker(
    server_id: UUID,
    inventory_service: Annotated[InventoryService, Depends(get_inventory_service)],
    discovery_service: Annotated[HostDiscoveryService, Depends(get_host_discovery_service)],
) -> HostDockerRead:
    try:
        server = await inventory_service.get_server(server_id)
        return await discovery_service.docker(server)
    except ServerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except HostDiscoveryError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post(
    "/{server_id}/health-check",
    response_model=InventoryHealthCheckResult,
    dependencies=[Depends(require_operator)],
)
async def health_check_server(
    server_id: UUID,
    service: Annotated[InventoryHealthService, Depends(get_inventory_health_service)],
) -> InventoryHealthCheckResult:
    try:
        return await service.check_server(server_id)
    except ServerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "",
    response_model=ServerRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_operator)],
)
async def create_server(
    payload: ServerCreate,
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> ServerRead:
    try:
        return await service.create_server(payload)
    except InventoryConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/sync/proxmox/import",
    response_model=ServerRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_operator)],
)
async def import_proxmox_vm(
    payload: ProxmoxInventoryImport,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> ServerRead:
    integration_service = IntegrationService(
        IntegrationRepository(session),
        credential_service=CredentialService(repository=CredentialRepository(session)),
    )
    try:
        integration = await IntegrationRepository(session).get_by_id(payload.integration_id)
        if integration is None:
            raise IntegrationNotFoundError("Integration not found")
        proxmox_service = ProxmoxService(
            await integration_service.get_proxmox_adapter(payload.integration_id),
            integration_id=payload.integration_id,
            integration_name=integration.name,
        )
        discovered_vms = await proxmox_service.list_vms()
        discovered_vm = next(
            (
                vm
                for vm in discovered_vms
                if vm.vm_id == payload.vm_id
                and vm.node == payload.node
                and vm.type == payload.vm_type
            ),
            None,
        )
        return await service.import_proxmox_vm(payload, discovered_vm=discovered_vm)
    except InventoryConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IntegrationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ProxmoxConfigurationError, ProxmoxConnectionError) as exc:
        await service.mark_integration_resources_disconnected(payload.integration_id, error=str(exc))
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post(
    "/sync/proxmox/reconcile",
    response_model=list[ServerRead],
    dependencies=[Depends(require_operator)],
)
async def reconcile_proxmox_inventory(
    integration_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> list[ServerRead]:
    integration_service = IntegrationService(
        IntegrationRepository(session),
        credential_service=CredentialService(repository=CredentialRepository(session)),
    )
    try:
        integration = await IntegrationRepository(session).get_by_id(integration_id)
        if integration is None:
            raise IntegrationNotFoundError("Integration not found")
        await integration_service.mark_integration_syncing(integration)
        proxmox_service = ProxmoxService(
            await integration_service.get_proxmox_adapter(integration_id),
            integration_id=integration_id,
            integration_name=integration.name,
        )
        vms = await proxmox_service.list_vms()
        result = await service.reconcile_proxmox_inventory(vms, integration_id=integration_id)
        await integration_service.mark_integration_connected(integration)
        return result
    except IntegrationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ProxmoxConfigurationError, ProxmoxConnectionError) as exc:
        await service.mark_integration_resources_disconnected(integration_id, error=str(exc))
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.put(
    "/{server_id}",
    response_model=ServerRead,
    dependencies=[Depends(require_operator)],
)
async def update_server(
    server_id: UUID,
    payload: ServerUpdate,
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> ServerRead:
    try:
        return await service.update_server(server_id, payload)
    except ServerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InventoryConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete(
    "/{server_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_operator)],
)
async def delete_server(
    server_id: UUID,
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> None:
    try:
        await service.delete_server(server_id)
    except ServerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{server_id}/archive",
    response_model=ServerRead,
    dependencies=[Depends(require_operator)],
)
async def archive_server(
    server_id: UUID,
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> ServerRead:
    try:
        return await service.archive_server(server_id)
    except ServerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{server_id}/decommission",
    response_model=ServerRead,
    dependencies=[Depends(require_operator)],
)
async def decommission_server(
    server_id: UUID,
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> ServerRead:
    try:
        return await service.decommission_server(server_id)
    except ServerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{server_id}/restore",
    response_model=ServerRead,
    dependencies=[Depends(require_operator)],
)
async def restore_server(
    server_id: UUID,
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> ServerRead:
    try:
        return await service.restore_server(server_id)
    except ServerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{server_id}/unmanage",
    response_model=ServerRead,
    dependencies=[Depends(require_operator)],
)
async def unmanage_server(
    server_id: UUID,
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> ServerRead:
    try:
        return await service.mark_unmanaged(server_id)
    except ServerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
