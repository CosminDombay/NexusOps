from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db_session
from backend.app.modules.trash.schemas import TrashItemRead, TrashListRead, TrashUsageRead
from backend.app.modules.trash.service import (
    TrashItemInUseError,
    TrashItemNotFoundError,
    TrashOperationUnsupportedError,
    TrashService,
)

router = APIRouter()


async def get_trash_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TrashService:
    return TrashService(session)


@router.get("", response_model=TrashListRead)
async def list_trash(
    service: Annotated[TrashService, Depends(get_trash_service)],
) -> TrashListRead:
    return await service.list_trash()


@router.get("/{item_type}/{item_id}/references", response_model=TrashUsageRead)
async def trash_references(
    item_type: str,
    item_id: UUID,
    service: Annotated[TrashService, Depends(get_trash_service)],
) -> TrashUsageRead:
    try:
        return await service.references(item_type, item_id)
    except TrashOperationUnsupportedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except TrashItemNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{item_type}/{item_id}/restore", response_model=TrashItemRead)
async def restore_trash_item(
    item_type: str,
    item_id: UUID,
    service: Annotated[TrashService, Depends(get_trash_service)],
) -> TrashItemRead:
    try:
        return await service.restore(item_type, item_id)
    except TrashOperationUnsupportedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except TrashItemNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{item_type}/{item_id}/purge", status_code=status.HTTP_204_NO_CONTENT)
async def purge_trash_item(
    item_type: str,
    item_id: UUID,
    service: Annotated[TrashService, Depends(get_trash_service)],
) -> None:
    try:
        await service.purge(item_type, item_id)
    except TrashItemInUseError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except TrashOperationUnsupportedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except TrashItemNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
