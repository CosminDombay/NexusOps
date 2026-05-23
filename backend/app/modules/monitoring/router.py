from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db_session
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.integrations.repository import IntegrationRepository
from backend.app.modules.integrations.service import IntegrationService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.service import ServerNotFoundError
from backend.app.modules.auth.security.dependencies import require_operator
from backend.app.modules.monitoring.schemas import (
    MonitoringOverviewRead,
    MonitoringValidationRead,
    PrometheusHealthRead,
    ServerMetricsRead,
)
from backend.app.modules.monitoring.service import MonitoringService

router = APIRouter()


async def get_monitoring_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MonitoringService:
    return MonitoringService(
        ServerRepository(session),
        integration_service=IntegrationService(
            IntegrationRepository(session),
            credential_service=CredentialService(repository=CredentialRepository(session)),
        ),
        credential_service=CredentialService(repository=CredentialRepository(session)),
    )


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
    providers = await service.snapshot_provider_statuses()
    prometheus = next(provider for provider in providers if provider.provider_type == "prometheus")
    grafana = next((provider for provider in providers if provider.provider_type == "grafana"), None)
    return PrometheusHealthRead(
        configured=prometheus.configured,
        reachable=prometheus.reachable,
        error=prometheus.error,
        integration_id=prometheus.integration_id,
        prometheus_url=prometheus.url,
        grafana_url=grafana.url if grafana else None,
        loki_url=None,
        providers=providers,
    )


@router.post(
    "/validate",
    response_model=MonitoringValidationRead,
    dependencies=[Depends(require_operator)],
)
async def validate_monitoring(
    service: Annotated[MonitoringService, Depends(get_monitoring_service)],
) -> MonitoringValidationRead:
    return await service.validate_all()


@router.post(
    "/servers/{server_id}/validate",
    response_model=MonitoringValidationRead,
    dependencies=[Depends(require_operator)],
)
async def validate_server_monitoring(
    server_id: UUID,
    service: Annotated[MonitoringService, Depends(get_monitoring_service)],
) -> MonitoringValidationRead:
    try:
        return await service.validate_server(server_id)
    except ServerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
