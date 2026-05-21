from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db_session
from backend.app.modules.auth.security.dependencies import require_operator
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.runtime_state.repository import (
    NodeRuntimeSnapshotRepository,
    RuntimeRefreshEventRepository,
    RuntimeRefreshStatusRepository,
)
from backend.app.modules.runtime_state.schemas import RuntimeRefreshStatusRead
from backend.app.modules.runtime_state.snapshots import RuntimeSnapshotService

router = APIRouter()


async def get_runtime_snapshot_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RuntimeSnapshotService:
    return RuntimeSnapshotService(
        NodeRuntimeSnapshotRepository(session),
        status_repository=RuntimeRefreshStatusRepository(session),
        event_repository=RuntimeRefreshEventRepository(session),
    )


@router.get("/refresh-status", response_model=list[RuntimeRefreshStatusRead])
async def list_refresh_statuses(
    service: Annotated[RuntimeSnapshotService, Depends(get_runtime_snapshot_service)],
) -> list[RuntimeRefreshStatusRead]:
    return await service.list_refresh_statuses()


@router.post(
    "/refresh/inventory",
    response_model=list[RuntimeRefreshStatusRead],
    dependencies=[Depends(require_operator)],
)
async def refresh_inventory_snapshots(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[RuntimeSnapshotService, Depends(get_runtime_snapshot_service)],
) -> list[RuntimeRefreshStatusRead]:
    servers = await ServerRepository(session).list(include_inactive=True)
    await service.refresh_inventory_snapshots(servers)
    return await service.list_refresh_statuses()
