from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db_session
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.service import ServerNotFoundError
from backend.app.modules.monitoring.schemas import (
    MonitoringOverviewRead,
    PrometheusHealthRead,
    ServerMetricsRead,
)
from backend.app.modules.monitoring.service import MonitoringService

router = APIRouter()


async def get_monitoring_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MonitoringService:
    return MonitoringService(ServerRepository(session))


@router.get("/overview", response_model=MonitoringOverviewRead)
async def get_overview(
    service: Annotated[MonitoringService, Depends(get_monitoring_service)],
) -> MonitoringOverviewRead:
    return await service.overview()


@router.get("/servers/{server_id}/metrics", response_model=ServerMetricsRead)
async def get_server_metrics(
    server_id: UUID,
    service: Annotated[MonitoringService, Depends(get_monitoring_service)],
) -> ServerMetricsRead:
    try:
        return await service.server_metrics(server_id)
    except ServerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/prometheus/health", response_model=PrometheusHealthRead)
async def get_prometheus_health(
    service: Annotated[MonitoringService, Depends(get_monitoring_service)],
) -> PrometheusHealthRead:
    return await service.prometheus_health()
