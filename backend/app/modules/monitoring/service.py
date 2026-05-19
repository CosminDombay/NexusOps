from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx

from backend.app.common.constants import InventoryHealthStatus
from backend.app.core.config import settings
from backend.app.modules.integrations.models import IntegrationProviderType
from backend.app.modules.integrations.service import IntegrationService, ProviderConnectionConfig
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.service import ServerNotFoundError
from backend.app.modules.monitoring.schemas import (
    MonitoringOverviewRead,
    MonitoringProviderStatusRead,
    PrometheusHealthRead,
    ServerMetricsRead,
)


class MonitoringService:
    """Prometheus HTTP API integration for lightweight server metrics."""

    def __init__(self, server_repository: ServerRepository, integration_service: IntegrationService) -> None:
        self.server_repository = server_repository
        self.integration_service = integration_service

    async def prometheus_health(self) -> PrometheusHealthRead:
        providers = await self.provider_statuses()
        prometheus = _provider_status(providers, IntegrationProviderType.PROMETHEUS)
        configs = await self._provider_configs()
        return PrometheusHealthRead(
            configured=prometheus.configured,
            reachable=prometheus.reachable,
            error=prometheus.error,
            integration_id=prometheus.integration_id,
            prometheus_url=prometheus.url,
            grafana_url=configs.get(IntegrationProviderType.GRAFANA).base_url
            if configs.get(IntegrationProviderType.GRAFANA)
            else None,
            loki_url=configs.get(IntegrationProviderType.LOKI).base_url
            if configs.get(IntegrationProviderType.LOKI)
            else None,
            providers=providers,
        )

    async def server_metrics(self, server_id: UUID) -> ServerMetricsRead:
        server = await self.server_repository.get_by_id(server_id)
        if server is None:
            raise ServerNotFoundError("Server not found")
        configs = await self._provider_configs()
        prometheus_config = configs.get(IntegrationProviderType.PROMETHEUS)
        metrics, metrics_error = await self._fetch_metrics(server.ip_address, prometheus_config)
        return ServerMetricsRead(
            server_id=server.id,
            hostname=server.hostname,
            ip_address=server.ip_address,
            online=server.last_health_status == InventoryHealthStatus.ONLINE,
            cpu_usage_percent=metrics.get("cpu"),
            memory_usage_percent=metrics.get("memory"),
            disk_usage_percent=metrics.get("disk"),
            uptime_seconds=metrics.get("uptime"),
            grafana_url=self._grafana_url(configs.get(IntegrationProviderType.GRAFANA), server.hostname),
            prometheus_url=self._prometheus_url(prometheus_config, server.ip_address),
            loki_url=self._loki_url(configs.get(IntegrationProviderType.LOKI), server.hostname),
            metrics_error=metrics_error,
            collected_at=datetime.now(UTC),
        )

    async def overview(self) -> MonitoringOverviewRead:
        servers = await self.server_repository.list()
        configs = await self._provider_configs()
        providers = await self.provider_statuses(configs)
        server_metrics = []
        for server in servers:
            try:
                metrics, metrics_error = await self._fetch_metrics(
                    server.ip_address,
                    configs.get(IntegrationProviderType.PROMETHEUS),
                )
                server_metrics.append(
                    ServerMetricsRead(
                        server_id=server.id,
                        hostname=server.hostname,
                        ip_address=server.ip_address,
                        online=server.last_health_status == InventoryHealthStatus.ONLINE,
                        cpu_usage_percent=metrics.get("cpu"),
                        memory_usage_percent=metrics.get("memory"),
                        disk_usage_percent=metrics.get("disk"),
                        uptime_seconds=metrics.get("uptime"),
                        grafana_url=self._grafana_url(configs.get(IntegrationProviderType.GRAFANA), server.hostname),
                        prometheus_url=self._prometheus_url(configs.get(IntegrationProviderType.PROMETHEUS), server.ip_address),
                        loki_url=self._loki_url(configs.get(IntegrationProviderType.LOKI), server.hostname),
                        metrics_error=metrics_error,
                        collected_at=datetime.now(UTC),
                    )
                )
            except Exception as exc:
                server_metrics.append(
                    ServerMetricsRead(
                        server_id=server.id,
                        hostname=server.hostname,
                        ip_address=server.ip_address,
                        online=False,
                        grafana_url=self._grafana_url(configs.get(IntegrationProviderType.GRAFANA), server.hostname),
                        prometheus_url=self._prometheus_url(configs.get(IntegrationProviderType.PROMETHEUS), server.ip_address),
                        loki_url=self._loki_url(configs.get(IntegrationProviderType.LOKI), server.hostname),
                        metrics_error=str(exc),
                        collected_at=datetime.now(UTC),
                    )
                )
        online_count = sum(1 for server in server_metrics if server.online)
        return MonitoringOverviewRead(
            total_servers=len(server_metrics),
            online_servers=online_count,
            offline_servers=len(server_metrics) - online_count,
            providers=providers,
            servers=server_metrics,
        )

    async def provider_statuses(
        self,
        configs: dict[IntegrationProviderType, ProviderConnectionConfig | None] | None = None,
    ) -> list[MonitoringProviderStatusRead]:
        configs = configs or await self._provider_configs()
        return [
            await self._provider_status(IntegrationProviderType.PROMETHEUS, configs.get(IntegrationProviderType.PROMETHEUS), "/-/healthy"),
            await self._provider_status(IntegrationProviderType.GRAFANA, configs.get(IntegrationProviderType.GRAFANA), "/api/health"),
            await self._provider_status(IntegrationProviderType.LOKI, configs.get(IntegrationProviderType.LOKI), "/ready"),
        ]

    async def _provider_configs(self) -> dict[IntegrationProviderType, ProviderConnectionConfig | None]:
        return {
            provider_type: await self.integration_service.get_provider_connection_config(
                provider_type,
                default_timeout_seconds=settings.monitoring_timeout_seconds,
            )
            for provider_type in (
                IntegrationProviderType.PROMETHEUS,
                IntegrationProviderType.GRAFANA,
                IntegrationProviderType.LOKI,
            )
        }

    async def _provider_status(
        self,
        provider_type: IntegrationProviderType,
        config: ProviderConnectionConfig | None,
        health_path: str,
    ) -> MonitoringProviderStatusRead:
        if config is None:
            return MonitoringProviderStatusRead(
                provider_type=provider_type.value,
                configured=False,
                reachable=False,
                error=f"{provider_type.value} integration is not configured or is disabled",
            )
        try:
            async with httpx.AsyncClient(
                timeout=config.timeout_seconds,
                verify=config.verify_ssl,
            ) as client:
                response = await client.get(f"{config.base_url}{health_path}", headers=config.headers)
                response.raise_for_status()
        except Exception as exc:
            return MonitoringProviderStatusRead(
                provider_type=provider_type.value,
                configured=True,
                reachable=False,
                integration_id=config.integration_id,
                url=config.base_url,
                error=str(exc),
            )
        return MonitoringProviderStatusRead(
            provider_type=provider_type.value,
            configured=True,
            reachable=True,
            integration_id=config.integration_id,
            url=config.base_url,
        )

    async def _fetch_metrics(
        self,
        ip_address: str,
        prometheus_config: ProviderConnectionConfig | None,
    ) -> tuple[dict[str, float | None], str | None]:
        empty = {"cpu": None, "memory": None, "disk": None, "uptime": None}
        if prometheus_config is None:
            return empty, "Prometheus integration is not configured or is disabled"

        queries = {
            "cpu": f'100 - (avg by(instance) (rate(node_cpu_seconds_total{{mode="idle",instance=~"{ip_address}.*"}}[5m])) * 100)',
            "memory": f'(1 - (node_memory_MemAvailable_bytes{{instance=~"{ip_address}.*"}} / node_memory_MemTotal_bytes{{instance=~"{ip_address}.*"}})) * 100',
            "disk": f'100 - ((node_filesystem_avail_bytes{{mountpoint="/",instance=~"{ip_address}.*"}} * 100) / node_filesystem_size_bytes{{mountpoint="/",instance=~"{ip_address}.*"}})',
            "uptime": f'time() - node_boot_time_seconds{{instance=~"{ip_address}.*"}}',
        }
        metrics: dict[str, float | None] = {}
        errors: list[str] = []
        async with httpx.AsyncClient(
            timeout=prometheus_config.timeout_seconds,
            verify=prometheus_config.verify_ssl,
        ) as client:
            for key, query in queries.items():
                try:
                    response = await client.get(
                        f"{prometheus_config.base_url}/api/v1/query",
                        params={"query": query},
                        headers=prometheus_config.headers,
                    )
                    response.raise_for_status()
                    metrics[key] = self._first_value(response.json())
                except Exception as exc:
                    metrics[key] = None
                    errors.append(f"{key}: {exc}")
        return metrics, "; ".join(errors) if errors else None

    @staticmethod
    def _first_value(payload: dict[str, Any]) -> float | None:
        result = payload.get("data", {}).get("result", [])
        if not result:
            return None
        value = result[0].get("value", [])
        if len(value) < 2:
            return None
        try:
            return float(value[1])
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _grafana_url(config: ProviderConnectionConfig | None, hostname: str) -> str | None:
        if config is None:
            return None
        return f"{config.base_url}/d/node-exporter?var-node={hostname}"

    @staticmethod
    def _prometheus_url(config: ProviderConnectionConfig | None, ip_address: str) -> str | None:
        if config is None:
            return None
        return f"{config.base_url}/graph?g0.expr=up%7Binstance%3D~%22{ip_address}.*%22%7D"

    @staticmethod
    def _loki_url(config: ProviderConnectionConfig | None, hostname: str) -> str | None:
        if config is None:
            return None
        return f"{config.base_url}/explore?query=%7Bhost%3D%22{hostname}%22%7D"


def _provider_status(
    providers: list[MonitoringProviderStatusRead],
    provider_type: IntegrationProviderType,
) -> MonitoringProviderStatusRead:
    return next(
        provider for provider in providers if provider.provider_type == provider_type.value
    )
