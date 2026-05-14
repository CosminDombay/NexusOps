from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.proxmox import HttpProxmoxAdapter
from backend.app.db.session import get_db_session
from backend.app.modules.inventory.models import ServerEnvironment
from backend.app.modules.inventory.health import InventoryHealthService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.schemas import (
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


@router.get("", response_model=list[ServerRead])
async def list_servers(
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    environment: ServerEnvironment | None = None,
    provider: str | None = None,
    search: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
) -> list[ServerRead]:
    return await service.list_servers(environment=environment, provider=provider, search=search)


@router.post("/health-check/bulk", response_model=list[InventoryHealthCheckResult])
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


@router.post("/{server_id}/health-check", response_model=InventoryHealthCheckResult)
async def health_check_server(
    server_id: UUID,
    service: Annotated[InventoryHealthService, Depends(get_inventory_health_service)],
) -> InventoryHealthCheckResult:
    try:
        return await service.check_server(server_id)
    except ServerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("", response_model=ServerRead, status_code=status.HTTP_201_CREATED)
async def create_server(
    payload: ServerCreate,
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> ServerRead:
    try:
        return await service.create_server(payload)
    except InventoryConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/sync/proxmox/import", response_model=ServerRead, status_code=status.HTTP_201_CREATED)
async def import_proxmox_vm(
    payload: ProxmoxInventoryImport,
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> ServerRead:
    proxmox_service = ProxmoxService(HttpProxmoxAdapter())
    try:
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


@router.post("/sync/proxmox/reconcile", response_model=list[ServerRead])
async def reconcile_proxmox_inventory(
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> list[ServerRead]:
    proxmox_service = ProxmoxService(HttpProxmoxAdapter())
    vms = await proxmox_service.list_vms()
    return await service.reconcile_proxmox_inventory(vms)


@router.put("/{server_id}", response_model=ServerRead)
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


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(
    server_id: UUID,
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> None:
    try:
        await service.delete_server(server_id)
    except ServerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{server_id}/archive", response_model=ServerRead)
async def archive_server(
    server_id: UUID,
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> ServerRead:
    try:
        return await service.archive_server(server_id)
    except ServerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
