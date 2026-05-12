from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db_session
from backend.app.modules.inventory.models import ServerEnvironment
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.schemas import ServerCreate, ServerRead, ServerUpdate
from backend.app.modules.inventory.service import (
    InventoryConflictError,
    InventoryService,
    ServerNotFoundError,
)

router = APIRouter()


async def get_inventory_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InventoryService:
    return InventoryService(ServerRepository(session))


@router.get("", response_model=list[ServerRead])
async def list_servers(
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    environment: ServerEnvironment | None = None,
    provider: str | None = None,
    search: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
) -> list[ServerRead]:
    return await service.list_servers(environment=environment, provider=provider, search=search)


@router.get("/{server_id}", response_model=ServerRead)
async def get_server(
    server_id: UUID,
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> ServerRead:
    try:
        return await service.get_server(server_id)
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
