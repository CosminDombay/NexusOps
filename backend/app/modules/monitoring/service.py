from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx

from backend.app.common.constants import InventoryHealthStatus
from backend.app.core.config import settings
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.service import ServerNotFoundError
from backend.app.modules.monitoring.schemas import (
    MonitoringOverviewRead,
    PrometheusHealthRead,
    ServerMetricsRead,
)


class MonitoringService:
    """Prometheus HTTP API integration for lightweight server metrics."""

    def __init__(self, server_repository: ServerRepository) -> None:
        self.server_repository = server_repository

    async def prometheus_health(self) -> PrometheusHealthRead:
        if not settings.prometheus_api_url:
            return PrometheusHealthRead(configured=False, reachable=False, error="Prometheus is not configured")
        try:
            async with httpx.AsyncClient(timeout=settings.monitoring_timeout_seconds) as client:
                response = await client.get(f"{settings.prometheus_api_url.rstrip('/')}/-/healthy")
                response.raise_for_status()
            return PrometheusHealthRead(configured=True, reachable=True)
        except Exception as exc:
            return PrometheusHealthRead(configured=True, reachable=False, error=str(exc))

    async def server_metrics(self, server_id: UUID) -> ServerMetricsRead:
        server = await self.server_repository.get_by_id(server_id)
        if server is None:
            raise ServerNotFoundError("Server not found")
        metrics = await self._fetch_metrics(server.ip_address)
        return ServerMetricsRead(
            server_id=server.id,
            hostname=server.hostname,
            ip_address=server.ip_address,
            online=server.last_health_status == InventoryHealthStatus.ONLINE,
            cpu_usage_percent=metrics.get("cpu"),
            memory_usage_percent=metrics.get("memory"),
            disk_usage_percent=metrics.get("disk"),
            uptime_seconds=metrics.get("uptime"),
            grafana_url=self._grafana_url(server.hostname),
            collected_at=datetime.now(UTC),
        )

    async def overview(self) -> MonitoringOverviewRead:
        servers = await self.server_repository.list()
        server_metrics = []
        for server in servers:
            try:
                server_metrics.append(await self.server_metrics(server.id))
            except Exception:
                server_metrics.append(
                    ServerMetricsRead(
                        server_id=server.id,
                        hostname=server.hostname,
                        ip_address=server.ip_address,
                        online=False,
                        grafana_url=self._grafana_url(server.hostname),
                        collected_at=datetime.now(UTC),
                    )
                )
        online_count = sum(1 for server in server_metrics if server.online)
        return MonitoringOverviewRead(
            total_servers=len(server_metrics),
            online_servers=online_count,
            offline_servers=len(server_metrics) - online_count,
            servers=server_metrics,
        )

    async def _fetch_metrics(self, ip_address: str) -> dict[str, float | None]:
        if not settings.prometheus_api_url:
            return {"cpu": None, "memory": None, "disk": None, "uptime": None}

        queries = {
            "cpu": f'100 - (avg by(instance) (rate(node_cpu_seconds_total{{mode="idle",instance=~"{ip_address}.*"}}[5m])) * 100)',
            "memory": f'(1 - (node_memory_MemAvailable_bytes{{instance=~"{ip_address}.*"}} / node_memory_MemTotal_bytes{{instance=~"{ip_address}.*"}})) * 100',
            "disk": f'100 - ((node_filesystem_avail_bytes{{mountpoint="/",instance=~"{ip_address}.*"}} * 100) / node_filesystem_size_bytes{{mountpoint="/",instance=~"{ip_address}.*"}})',
            "uptime": f'time() - node_boot_time_seconds{{instance=~"{ip_address}.*"}}',
        }
        metrics: dict[str, float | None] = {}
        async with httpx.AsyncClient(timeout=settings.monitoring_timeout_seconds) as client:
            for key, query in queries.items():
                try:
                    response = await client.get(
                        f"{settings.prometheus_api_url.rstrip('/')}/api/v1/query",
                        params={"query": query},
                    )
                    response.raise_for_status()
                    metrics[key] = self._first_value(response.json())
                except Exception:
                    metrics[key] = None
        return metrics

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
    def _grafana_url(hostname: str) -> str | None:
        if not settings.grafana_base_url:
            return None
        return f"{settings.grafana_base_url.rstrip('/')}/d/node-exporter?var-node={hostname}"
