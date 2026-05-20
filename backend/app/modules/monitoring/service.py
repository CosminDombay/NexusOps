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
        readiness = await self._node_observability_readiness(
            server.hostname,
            server.ip_address,
            metrics,
            metrics_error,
            configs,
        )
        return ServerMetricsRead(
            server_id=server.id,
            hostname=server.hostname,
            ip_address=server.ip_address,
            online=server.last_health_status == InventoryHealthStatus.ONLINE,
            cpu_usage_percent=metrics.get("cpu"),
            memory_usage_percent=metrics.get("memory"),
            disk_usage_percent=metrics.get("disk"),
            uptime_seconds=metrics.get("uptime"),
            grafana_url=self._grafana_url(configs.get(IntegrationProviderType.GRAFANA)),
            prometheus_url=self._prometheus_url(prometheus_config, server.ip_address),
            loki_url=self._loki_url(configs.get(IntegrationProviderType.LOKI)),
            advanced_metrics_url=self._grafana_url(configs.get(IntegrationProviderType.GRAFANA)),
            advanced_logs_url=self._grafana_url(configs.get(IntegrationProviderType.GRAFANA)),
            metrics_error=metrics_error,
            **readiness,
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
                readiness = await self._node_observability_readiness(
                    server.hostname,
                    server.ip_address,
                    metrics,
                    metrics_error,
                    configs,
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
                        grafana_url=self._grafana_url(configs.get(IntegrationProviderType.GRAFANA)),
                        prometheus_url=self._prometheus_url(configs.get(IntegrationProviderType.PROMETHEUS), server.ip_address),
                        loki_url=self._loki_url(configs.get(IntegrationProviderType.LOKI)),
                        advanced_metrics_url=self._grafana_url(configs.get(IntegrationProviderType.GRAFANA)),
                        advanced_logs_url=self._grafana_url(configs.get(IntegrationProviderType.GRAFANA)),
                        metrics_error=metrics_error,
                        **readiness,
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
                        grafana_url=self._grafana_url(configs.get(IntegrationProviderType.GRAFANA)),
                        prometheus_url=self._prometheus_url(configs.get(IntegrationProviderType.PROMETHEUS), server.ip_address),
                        loki_url=self._loki_url(configs.get(IntegrationProviderType.LOKI)),
                        advanced_metrics_url=self._grafana_url(configs.get(IntegrationProviderType.GRAFANA)),
                        advanced_logs_url=self._grafana_url(configs.get(IntegrationProviderType.GRAFANA)),
                        metrics_error=str(exc),
                        monitoring_state="monitoring_unavailable",
                        readiness_reasons=[str(exc)],
                        collected_at=datetime.now(UTC),
                    )
                )
        online_count = sum(1 for server in server_metrics if server.online)
        return MonitoringOverviewRead(
            total_servers=len(server_metrics),
            online_servers=online_count,
            offline_servers=len(server_metrics) - online_count,
            observable_servers=sum(1 for server in server_metrics if server.monitoring_state == "monitoring_ready"),
            degraded_servers=sum(1 for server in server_metrics if server.monitoring_state in {"monitoring_partial", "stale_metrics"}),
            metrics_missing_servers=sum(1 for server in server_metrics if not server.metrics_available),
            logs_missing_servers=sum(1 for server in server_metrics if not server.logs_available),
            stale_metrics_servers=sum(1 for server in server_metrics if server.stale_metrics),
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

    async def _node_observability_readiness(
        self,
        hostname: str,
        ip_address: str,
        metrics: dict[str, float | None],
        metrics_error: str | None,
        configs: dict[IntegrationProviderType, ProviderConnectionConfig | None],
    ) -> dict[str, object]:
        prometheus_config = configs.get(IntegrationProviderType.PROMETHEUS)
        loki_config = configs.get(IntegrationProviderType.LOKI)
        metrics_available = any(value is not None for value in metrics.values())
        scrape_health = await self._prometheus_target_health(ip_address, prometheus_config)
        node_exporter_detected = scrape_health in {"up", "unknown"} and metrics_available
        cadvisor_detected = await self._prometheus_has_series(
            prometheus_config,
            f'container_last_seen{{instance=~"{ip_address}.*"}}',
        )
        logs_available, logs_error = await self._loki_stream_present(hostname, ip_address, loki_config)
        promtail_detected = logs_available
        stale_metrics = await self._prometheus_has_stale_metrics(ip_address, prometheus_config)

        reasons: list[str] = []
        if metrics_error:
            reasons.append(metrics_error)
        if not metrics_available:
            reasons.append("metrics_missing")
        if not node_exporter_detected:
            reasons.append("node_exporter_missing")
        if scrape_health not in {"up", "unknown"}:
            reasons.append(f"scrape_{scrape_health}")
        if stale_metrics:
            reasons.append("stale_metrics")
        if logs_error:
            reasons.append(logs_error)
        if not logs_available:
            reasons.append("logs_missing")

        if metrics_available and logs_available and not stale_metrics:
            state = "monitoring_ready"
        elif stale_metrics:
            state = "stale_metrics"
        elif metrics_available or logs_available:
            state = "monitoring_partial"
        else:
            state = "monitoring_missing"

        return {
            "metrics_available": metrics_available,
            "logs_available": logs_available,
            "node_exporter_detected": node_exporter_detected,
            "cadvisor_detected": cadvisor_detected,
            "promtail_detected": promtail_detected,
            "scrape_target_health": scrape_health,
            "stale_metrics": stale_metrics,
            "logs_error": logs_error,
            "monitoring_state": state,
            "readiness_reasons": list(dict.fromkeys(reasons)),
        }

    async def _prometheus_target_health(
        self,
        ip_address: str,
        config: ProviderConnectionConfig | None,
    ) -> str:
        if config is None:
            return "unconfigured"
        try:
            async with httpx.AsyncClient(timeout=config.timeout_seconds, verify=config.verify_ssl) as client:
                response = await client.get(
                    f"{config.base_url}/api/v1/query",
                    params={"query": f'up{{instance=~"{ip_address}.*"}}'},
                    headers=config.headers,
                )
                response.raise_for_status()
                value = self._first_value(response.json())
                if value == 1:
                    return "up"
                if value == 0:
                    return "down"
        except Exception:
            return "unavailable"
        return "missing"

    async def _prometheus_has_series(
        self,
        config: ProviderConnectionConfig | None,
        query: str,
    ) -> bool:
        if config is None:
            return False
        try:
            async with httpx.AsyncClient(timeout=config.timeout_seconds, verify=config.verify_ssl) as client:
                response = await client.get(
                    f"{config.base_url}/api/v1/query",
                    params={"query": query},
                    headers=config.headers,
                )
                response.raise_for_status()
                return bool(response.json().get("data", {}).get("result", []))
        except Exception:
            return False

    async def _prometheus_has_stale_metrics(
        self,
        ip_address: str,
        config: ProviderConnectionConfig | None,
    ) -> bool:
        if config is None:
            return False
        try:
            async with httpx.AsyncClient(timeout=config.timeout_seconds, verify=config.verify_ssl) as client:
                response = await client.get(
                    f"{config.base_url}/api/v1/query",
                    params={"query": f'node_boot_time_seconds{{instance=~"{ip_address}.*"}}'},
                    headers=config.headers,
                )
                response.raise_for_status()
                sample_time = self._first_timestamp(response.json())
                if sample_time is None:
                    return False
                return (datetime.now(UTC).timestamp() - sample_time) > 900
        except Exception:
            return False

    async def _loki_stream_present(
        self,
        hostname: str,
        ip_address: str,
        config: ProviderConnectionConfig | None,
    ) -> tuple[bool, str | None]:
        if config is None:
            return False, "loki_not_configured"
        queries = [f'{{host="{hostname}"}}', f'{{hostname="{hostname}"}}', f'{{instance=~"{ip_address}.*"}}']
        try:
            async with httpx.AsyncClient(timeout=config.timeout_seconds, verify=config.verify_ssl) as client:
                for query in queries:
                    response = await client.get(
                        f"{config.base_url}/loki/api/v1/query",
                        params={"query": query},
                        headers=config.headers,
                    )
                    response.raise_for_status()
                    if response.json().get("data", {}).get("result", []):
                        return True, None
        except Exception as exc:
            return False, f"loki_unavailable: {exc}"
        return False, "log_stream_missing"

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
    def _first_timestamp(payload: dict[str, Any]) -> float | None:
        result = payload.get("data", {}).get("result", [])
        if not result:
            return None
        value = result[0].get("value", [])
        if not value:
            return None
        try:
            return float(value[0])
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _grafana_url(config: ProviderConnectionConfig | None) -> str | None:
        if config is None:
            return None
        return config.base_url

    @staticmethod
    def _prometheus_url(config: ProviderConnectionConfig | None, ip_address: str) -> str | None:
        if config is None:
            return None
        return f"{config.base_url}/graph?g0.expr=up%7Binstance%3D~%22{ip_address}.*%22%7D"

    @staticmethod
    def _loki_url(config: ProviderConnectionConfig | None) -> str | None:
        if config is None:
            return None
        return config.base_url


def _provider_status(
    providers: list[MonitoringProviderStatusRead],
    provider_type: IntegrationProviderType,
) -> MonitoringProviderStatusRead:
    return next(
        provider for provider in providers if provider.provider_type == provider_type.value
    )
