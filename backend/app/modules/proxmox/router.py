from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.proxmox import (
    ProxmoxConfigurationError,
    ProxmoxConnectionError,
)
from backend.app.modules.integrations.models import IntegrationProviderType
from backend.app.db.session import get_db_session
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.integrations.repository import IntegrationRepository
from backend.app.modules.integrations.service import IntegrationNotFoundError, IntegrationService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.service import InventoryService
from backend.app.modules.auth.security.dependencies import require_operator
from backend.app.modules.proxmox.schemas import (
    ProxmoxClusterSummaryRead,
    ProxmoxDashboardRead,
    ProxmoxGuestSyncRead,
    ProxmoxHostSyncRead,
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
    integration = await integration_service.get_enabled_provider(IntegrationProviderType.PROXMOX)
    if integration is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="No enabled Proxmox integration is configured")
    return ProxmoxService(
        await integration_service.get_proxmox_adapter(integration.id),
        server_repository=ServerRepository(session),
        integration_id=integration.id,
        integration_name=integration.name,
    )


async def get_proxmox_services(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[tuple[ProxmoxService, IntegrationService, object]]:
    integration_service = IntegrationService(
        IntegrationRepository(session),
        credential_service=CredentialService(repository=CredentialRepository(session)),
    )
    services = []
    for integration in await integration_service.list_enabled_providers(IntegrationProviderType.PROXMOX):
        try:
            adapter = await integration_service.get_proxmox_adapter(integration.id)
        except IntegrationNotFoundError:
            continue
        services.append(
            (
                ProxmoxService(
                    adapter,
                    server_repository=ServerRepository(session),
                    integration_id=integration.id,
                    integration_name=integration.name,
                ),
                integration_service,
                integration,
            )
        )
    return services


async def _service_for_integration(
    session: AsyncSession,
    integration_id: UUID | None,
) -> ProxmoxService:
    integration_service = IntegrationService(
        IntegrationRepository(session),
        credential_service=CredentialService(repository=CredentialRepository(session)),
    )
    integration = (
        await IntegrationRepository(session).get_by_id(integration_id)
        if integration_id
        else await integration_service.get_enabled_provider(IntegrationProviderType.PROXMOX)
    )
    if integration is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="No enabled Proxmox integration is configured")
    return ProxmoxService(
        await integration_service.get_proxmox_adapter(integration.id),
        server_repository=ServerRepository(session),
        integration_id=integration.id,
        integration_name=integration.name,
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
    services: Annotated[list[tuple[ProxmoxService, IntegrationService, object]], Depends(get_proxmox_services)],
) -> list[ProxmoxNodeRead]:
    nodes: list[ProxmoxNodeRead] = []
    for service, integration_service, integration in services:
        try:
            await integration_service.mark_integration_syncing(integration)
            nodes.extend(await service.get_nodes())
            await integration_service.mark_integration_connected(integration)
        except (ProxmoxConfigurationError, ProxmoxConnectionError) as exc:
            await integration_service.mark_integration_error(integration, str(exc))
            await InventoryService(ServerRepository(integration_service.repository.session)).mark_integration_resources_disconnected(integration.id, error=str(exc))
    return nodes


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
    services: Annotated[list[tuple[ProxmoxService, IntegrationService, object]], Depends(get_proxmox_services)],
) -> list[ProxmoxVmRead]:
    vms: list[ProxmoxVmRead] = []
    for service, integration_service, integration in services:
        try:
            await integration_service.mark_integration_syncing(integration)
            vms.extend(await service.list_vms())
            await integration_service.mark_integration_connected(integration)
        except (ProxmoxConfigurationError, ProxmoxConnectionError) as exc:
            await integration_service.mark_integration_error(integration, str(exc))
            await InventoryService(ServerRepository(integration_service.repository.session)).mark_integration_resources_disconnected(integration.id, error=str(exc))
    return vms


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
    services: Annotated[list[tuple[ProxmoxService, IntegrationService, object]], Depends(get_proxmox_services)],
) -> ProxmoxClusterSummaryRead:
    dashboards = []
    for service, integration_service, integration in services:
        try:
            await integration_service.mark_integration_syncing(integration)
            dashboards.append(await service.get_dashboard())
            await integration_service.mark_integration_connected(integration)
        except (ProxmoxConfigurationError, ProxmoxConnectionError) as exc:
            await integration_service.mark_integration_error(integration, str(exc))
            await InventoryService(ServerRepository(integration_service.repository.session)).mark_integration_resources_disconnected(integration.id, error=str(exc))
    return ProxmoxClusterSummaryRead(
        node_count=sum(item.summary.node_count for item in dashboards),
        online_node_count=sum(item.summary.online_node_count for item in dashboards),
        vm_count=sum(item.summary.vm_count for item in dashboards),
        running_vm_count=sum(item.summary.running_vm_count for item in dashboards),
        stopped_vm_count=sum(item.summary.stopped_vm_count for item in dashboards),
        cpu_usage=None,
        memory_used=sum(item.summary.memory_used or 0 for item in dashboards) or None,
        memory_total=sum(item.summary.memory_total or 0 for item in dashboards) or None,
    )


@router.get("/dashboard", response_model=ProxmoxDashboardRead)
async def get_dashboard(
    services: Annotated[list[tuple[ProxmoxService, IntegrationService, object]], Depends(get_proxmox_services)],
) -> ProxmoxDashboardRead:
    nodes: list[ProxmoxNodeRead] = []
    vms: list[ProxmoxVmRead] = []
    for service, integration_service, integration in services:
        try:
            await integration_service.mark_integration_syncing(integration)
            dashboard = await service.get_dashboard()
            nodes.extend(dashboard.nodes)
            vms.extend(dashboard.vms)
            await integration_service.mark_integration_connected(integration)
        except (ProxmoxConfigurationError, ProxmoxConnectionError) as exc:
            await integration_service.mark_integration_error(integration, str(exc))
            await InventoryService(ServerRepository(integration_service.repository.session)).mark_integration_resources_disconnected(integration.id, error=str(exc))
    cpu_values = [node.cpu_usage for node in nodes if node.cpu_usage is not None]
    return ProxmoxDashboardRead(
        summary=ProxmoxClusterSummaryRead(
            node_count=len(nodes),
            online_node_count=sum(1 for node in nodes if node.status == "online"),
            vm_count=len(vms),
            running_vm_count=sum(1 for vm in vms if vm.status == "running"),
            stopped_vm_count=sum(1 for vm in vms if vm.status == "stopped"),
            cpu_usage=sum(cpu_values) / len(cpu_values) if cpu_values else None,
            memory_used=sum(node.memory_used or 0 for node in nodes) or None,
            memory_total=sum(node.memory_total or 0 for node in nodes) or None,
        ),
        nodes=nodes,
        vms=vms,
    )


@router.post(
    "/hosts/sync",
    response_model=ProxmoxHostSyncRead,
    dependencies=[Depends(require_operator)],
)
async def sync_proxmox_hosts(
    service: Annotated[ProxmoxService, Depends(get_proxmox_service)],
) -> ProxmoxHostSyncRead:
    try:
        return await service.sync_hosts()
    except (
        ProxmoxConfigurationError,
        ProxmoxConnectionError,
        ProxmoxVmActionNotAllowedError,
    ) as exc:
        raise _map_proxmox_error(exc) from exc

@router.post(
    "/guests/sync",
    response_model=ProxmoxGuestSyncRead,
    dependencies=[Depends(require_operator)],
)
async def sync_proxmox_guests(
    service: Annotated[ProxmoxService, Depends(get_proxmox_service)],
) -> ProxmoxGuestSyncRead:
    try:
        return await service.sync_guests()
    except (
        ProxmoxConfigurationError,
        ProxmoxConnectionError,
        ProxmoxVmActionNotAllowedError,
    ) as exc:
        raise _map_proxmox_error(exc) from exc


@router.post(
    "/vms/{vm_id}/start",
    response_model=ProxmoxVmActionRead,
    dependencies=[Depends(require_operator)],
)
async def start_vm(
    vm_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    integration_id: UUID | None = None,
) -> ProxmoxVmActionRead:
    try:
        service = await _service_for_integration(session, integration_id)
        return await service.start_vm(vm_id)
    except (
        ProxmoxConfigurationError,
        ProxmoxConnectionError,
        ProxmoxVmActionNotAllowedError,
        ProxmoxVmNotFoundError,
    ) as exc:
        raise _map_proxmox_error(exc) from exc


@router.post(
    "/vms/{vm_id}/stop",
    response_model=ProxmoxVmActionRead,
    dependencies=[Depends(require_operator)],
)
async def stop_vm(
    vm_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    integration_id: UUID | None = None,
) -> ProxmoxVmActionRead:
    try:
        service = await _service_for_integration(session, integration_id)
        return await service.stop_vm(vm_id)
    except (
        ProxmoxConfigurationError,
        ProxmoxConnectionError,
        ProxmoxVmActionNotAllowedError,
        ProxmoxVmNotFoundError,
    ) as exc:
        raise _map_proxmox_error(exc) from exc


@router.post(
    "/vms/{vm_id}/reboot",
    response_model=ProxmoxVmActionRead,
    dependencies=[Depends(require_operator)],
)
async def reboot_vm(
    vm_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    integration_id: UUID | None = None,
) -> ProxmoxVmActionRead:
    try:
        service = await _service_for_integration(session, integration_id)
        return await service.reboot_vm(vm_id)
    except (
        ProxmoxConfigurationError,
        ProxmoxConnectionError,
        ProxmoxVmActionNotAllowedError,
        ProxmoxVmNotFoundError,
    ) as exc:
        raise _map_proxmox_error(exc) from exc


@router.post(
    "/vms/{vm_id}/shutdown",
    response_model=ProxmoxVmActionRead,
    dependencies=[Depends(require_operator)],
)
async def shutdown_vm(
    vm_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    integration_id: UUID | None = None,
) -> ProxmoxVmActionRead:
    try:
        service = await _service_for_integration(session, integration_id)
        return await service.shutdown_vm(vm_id)
    except (
        ProxmoxConfigurationError,
        ProxmoxConnectionError,
        ProxmoxVmActionNotAllowedError,
        ProxmoxVmNotFoundError,
    ) as exc:
        raise _map_proxmox_error(exc) from exc
