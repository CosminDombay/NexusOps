from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.proxmox import ProxmoxConfigurationError, ProxmoxConnectionError
from backend.app.common.constants import InventoryHealthStatus, InventorySyncStatus
from backend.app.db.session import get_db_session
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.integrations.repository import IntegrationRepository
from backend.app.modules.integrations.schemas import (
    IntegrationCreate,
    IntegrationRead,
    IntegrationTestRead,
    IntegrationUpdate,
)
from backend.app.modules.integrations.service import IntegrationNotFoundError, IntegrationService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.service import InventoryService
from backend.app.modules.proxmox.schemas import ProxmoxGuestSyncRead, ProxmoxHostSyncRead
from backend.app.modules.proxmox.service import ProxmoxService

router = APIRouter()


async def get_integration_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> IntegrationService:
    return IntegrationService(
        IntegrationRepository(session),
        credential_service=CredentialService(repository=CredentialRepository(session)),
    )


@router.get("", response_model=list[IntegrationRead])
async def list_integrations(
    service: Annotated[IntegrationService, Depends(get_integration_service)],
) -> list[IntegrationRead]:
    return await service.list_integrations()


@router.post("", response_model=IntegrationRead, status_code=status.HTTP_201_CREATED)
async def create_integration(
    payload: IntegrationCreate,
    service: Annotated[IntegrationService, Depends(get_integration_service)],
) -> IntegrationRead:
    return await service.create_integration(payload)


@router.put("/{integration_id}", response_model=IntegrationRead)
async def update_integration(
    integration_id: UUID,
    payload: IntegrationUpdate,
    service: Annotated[IntegrationService, Depends(get_integration_service)],
) -> IntegrationRead:
    try:
        return await service.update_integration(integration_id, payload)
    except IntegrationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(
    integration_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[IntegrationService, Depends(get_integration_service)],
) -> None:
    try:
        await _decommission_integration_hosts(session, integration_id)
        await service.delete_integration(integration_id)
    except IntegrationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{integration_id}/test", response_model=IntegrationTestRead)
async def test_integration(
    integration_id: UUID,
    service: Annotated[IntegrationService, Depends(get_integration_service)],
) -> IntegrationTestRead:
    try:
        return await service.test_integration(integration_id)
    except IntegrationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{integration_id}/sync/proxmox-hosts", response_model=ProxmoxHostSyncRead)
async def sync_proxmox_hosts(
    integration_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[IntegrationService, Depends(get_integration_service)],
) -> ProxmoxHostSyncRead:
    integration = await IntegrationRepository(session).get_by_id(integration_id)
    if integration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    try:
        await service.mark_integration_syncing(integration)
        adapter = await service.get_proxmox_adapter(integration_id)
        result = await ProxmoxService(
            adapter,
            server_repository=ServerRepository(session),
            integration_id=integration_id,
            integration_name=integration.name,
        ).sync_hosts()
        await service.mark_integration_connected(integration)
        return result
    except IntegrationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ProxmoxConfigurationError, ProxmoxConnectionError) as exc:
        await service.mark_integration_error(integration, str(exc))
        await InventoryService(ServerRepository(session)).mark_integration_resources_disconnected(integration_id, error=str(exc))
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/{integration_id}/sync/proxmox-guests", response_model=ProxmoxGuestSyncRead)
async def sync_proxmox_guests(
    integration_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[IntegrationService, Depends(get_integration_service)],
) -> ProxmoxGuestSyncRead:
    integration = await IntegrationRepository(session).get_by_id(integration_id)
    if integration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    try:
        await service.mark_integration_syncing(integration)
        adapter = await service.get_proxmox_adapter(integration_id)
        result = await ProxmoxService(
            adapter,
            server_repository=ServerRepository(session),
            integration_id=integration_id,
            integration_name=integration.name,
        ).sync_guests()
        await service.mark_integration_connected(integration)
        return result
    except IntegrationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ProxmoxConfigurationError, ProxmoxConnectionError) as exc:
        await service.mark_integration_error(integration, str(exc))
        await InventoryService(ServerRepository(session)).mark_integration_resources_disconnected(integration_id, error=str(exc))
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


async def _decommission_integration_hosts(session: AsyncSession, integration_id: UUID) -> None:
    repository = ServerRepository(session)
    for server in await repository.list_by_provider_integration("proxmox", integration_id):
        server.sync_status = InventorySyncStatus.DISCONNECTED
        server.sync_state = InventorySyncStatus.DISCONNECTED
        server.last_health_status = InventoryHealthStatus.SYNC_ERROR
        server.provider_metadata = {
            **server.provider_metadata,
            "disconnected_by_integration_delete": True,
        }
    await session.commit()
