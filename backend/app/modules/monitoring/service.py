from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx

from backend.app.common.constants import InventoryHealthStatus
from backend.app.core.config import settings
from backend.app.modules.integrations.models import IntegrationProviderType
from backend.app.modules.integrations.service import IntegrationService, ProviderConnectionConfig
from backend.app.modules.inventory.models import Server
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.service import ServerNotFoundError
from backend.app.modules.monitoring.schemas import (
    MonitoringOverviewRead,
    MonitoringProviderStatusRead,
    PrometheusHealthRead,
    ServerMetricsRead,
)
from backend.app.modules.runtime_state.repository import (
    NodeRuntimeSnapshotRepository,
    RuntimeRefreshStatusRepository,
)
from backend.app.modules.runtime_state.snapshots import RuntimeSnapshotService


class MonitoringService:
    """Observability readiness validation backed by runtime snapshots."""

    def __init__(self, server_repository: ServerRepository, integration_service: IntegrationService) -> None:
        self.server_repository = server_repository
        self.integration_service = integration_service
        self.runtime_snapshots = RuntimeSnapshotService(
            NodeRuntimeSnapshotRepository(server_repository.session),
            status_repository=RuntimeRefreshStatusRepository(server_repository.session),
        )

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
        monitoring_target = self._monitoring_target(server)
        monitoring_targets = [monitoring_target] if monitoring_target else []
        metrics = self._operational_summary(server)
        technical_details: list[str] = []
        readiness = await self._node_observability_readiness(
            server,
            monitoring_target,
            configs,
            technical_details=technical_details,
        )
        await self.runtime_snapshots.refresh_monitoring_snapshot(
            server,
            monitoring_targets=monitoring_targets,
            metrics=metrics,
            observability=readiness,
            metrics_error=None,
        )
        return ServerMetricsRead(
            server_id=server.id,
            hostname=server.hostname,
            ip_address=server.ip_address,
            monitoring_targets=monitoring_targets,
            online=server.last_health_status == InventoryHealthStatus.ONLINE,
            cpu_usage_percent=metrics.get("cpu"),
            memory_usage_percent=metrics.get("memory"),
            disk_usage_percent=metrics.get("disk"),
            uptime_seconds=metrics.get("uptime"),
            grafana_url=self._grafana_url(configs.get(IntegrationProviderType.GRAFANA)),
            prometheus_url=self._prometheus_url(prometheus_config, monitoring_targets),
            loki_url=self._loki_url(configs.get(IntegrationProviderType.LOKI)),
            advanced_metrics_url=self._grafana_url(configs.get(IntegrationProviderType.GRAFANA)),
            advanced_logs_url=self._grafana_url(configs.get(IntegrationProviderType.GRAFANA)),
            metrics_error=None,
            **readiness,
            collected_at=datetime.now(UTC),
        )

    async def overview(self) -> MonitoringOverviewRead:
        servers = await self.server_repository.list()
        await self.runtime_snapshots.attach_snapshots(servers)
        snapshot_map = await self.runtime_snapshots.snapshot_repository.list_by_node_ids(
            server.id for server in servers
        )
        configs = await self._provider_configs()
        providers = await self._snapshot_provider_statuses(configs)
        server_metrics = []
        for server in servers:
            snapshot = snapshot_map.get(server.id)
            runtime_state = getattr(server, "runtime_state", None)
            metrics = snapshot.metrics if snapshot is not None and isinstance(snapshot.metrics, dict) else {}
            observability = (
                snapshot.observability
                if snapshot is not None and isinstance(snapshot.observability, dict)
                else {}
            )
            monitoring_targets = (
                snapshot.monitoring_targets
                if snapshot is not None and snapshot.monitoring_targets
                else self._static_monitoring_targets(server)
            )
            monitoring_state = runtime_state.monitoring_state if runtime_state else "unknown"
            readiness_reasons = list(
                dict.fromkeys(
                    [
                        *observability.get("readiness_reasons", []),
                        *(runtime_state.degraded_reasons if runtime_state else []),
                    ]
                )
            )
            server_metrics.append(
                ServerMetricsRead(
                    server_id=server.id,
                    hostname=server.hostname,
                    ip_address=server.ip_address,
                    monitoring_targets=monitoring_targets,
                    monitoring_interface=_optional_str(observability.get("monitoring_interface")),
                    monitoring_strategy=_optional_str(observability.get("monitoring_strategy")) or "host",
                    online=runtime_state.ssh_state == "ready" if runtime_state else False,
                    cpu_usage_percent=_optional_float(metrics.get("cpu")),
                    memory_usage_percent=_optional_float(metrics.get("memory")),
                    disk_usage_percent=_optional_float(metrics.get("disk")),
                    uptime_seconds=_optional_float(metrics.get("uptime")),
                    grafana_url=self._grafana_url(configs.get(IntegrationProviderType.GRAFANA)),
                    prometheus_url=self._prometheus_url(configs.get(IntegrationProviderType.PROMETHEUS), monitoring_targets),
                    loki_url=self._loki_url(configs.get(IntegrationProviderType.LOKI)),
                    advanced_metrics_url=self._grafana_url(configs.get(IntegrationProviderType.GRAFANA)),
                    advanced_logs_url=self._grafana_url(configs.get(IntegrationProviderType.GRAFANA)),
                    metrics_error=None,
                    logs_error=None,
                    monitoring_state=monitoring_state,
                    monitoring_status=self._display_state(monitoring_state),
                    metrics_available=bool(observability.get("metrics_available")),
                    logs_available=bool(observability.get("logs_available")),
                    node_exporter_detected=bool(observability.get("node_exporter_detected")),
                    node_exporter_reachable=bool(observability.get("node_exporter_reachable")),
                    cadvisor_detected=bool(observability.get("cadvisor_detected")),
                    cadvisor_running=bool(observability.get("cadvisor_running")),
                    docker_runtime_available=bool(observability.get("docker_runtime_available")),
                    promtail_detected=bool(observability.get("promtail_detected")),
                    promtail_reachable=bool(observability.get("promtail_reachable")),
                    scrape_target_health=_optional_str(observability.get("scrape_target_health")) or "unknown",
                    stale_metrics=bool(observability.get("stale_metrics")),
                    readiness_reasons=readiness_reasons,
                    remediation=list(observability.get("remediation", [])),
                    technical_details=list(observability.get("technical_details", [])),
                    collected_at=snapshot.last_checked_at if snapshot and snapshot.last_checked_at else datetime.now(UTC),
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

    async def _snapshot_provider_statuses(
        self,
        configs: dict[IntegrationProviderType, ProviderConnectionConfig | None],
    ) -> list[MonitoringProviderStatusRead]:
        statuses = {
            status.scope: status
            for status in await self.runtime_snapshots.list_refresh_statuses()
        }
        monitoring_refresh = statuses.get("monitoring")
        provider_refresh = statuses.get("provider")
        return [
            self._snapshot_provider_status(
                IntegrationProviderType.PROMETHEUS,
                configs.get(IntegrationProviderType.PROMETHEUS),
                monitoring_refresh,
            ),
            self._snapshot_provider_status(
                IntegrationProviderType.GRAFANA,
                configs.get(IntegrationProviderType.GRAFANA),
                monitoring_refresh,
            ),
            self._snapshot_provider_status(
                IntegrationProviderType.LOKI,
                configs.get(IntegrationProviderType.LOKI),
                monitoring_refresh or provider_refresh,
            ),
        ]

    @staticmethod
    def _snapshot_provider_status(
        provider_type: IntegrationProviderType,
        config: ProviderConnectionConfig | None,
        refresh_status: object | None,
    ) -> MonitoringProviderStatusRead:
        if config is None:
            return MonitoringProviderStatusRead(
                provider_type=provider_type.value,
                configured=False,
                reachable=False,
                error=f"{provider_type.value} integration is not configured or is disabled",
            )
        status_value = getattr(refresh_status, "status", "unknown") if refresh_status else "unknown"
        return MonitoringProviderStatusRead(
            provider_type=provider_type.value,
            configured=True,
            reachable=status_value == "success",
            integration_id=config.integration_id,
            url=config.base_url,
            error=getattr(refresh_status, "last_error", None) if status_value == "failed" else None,
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
        except Exception:
            return MonitoringProviderStatusRead(
                provider_type=provider_type.value,
                configured=True,
                reachable=False,
                integration_id=config.integration_id,
                url=config.base_url,
                error=f"{provider_type.value}_unavailable",
            )
        return MonitoringProviderStatusRead(
            provider_type=provider_type.value,
            configured=True,
            reachable=True,
            integration_id=config.integration_id,
            url=config.base_url,
        )

    async def _node_observability_readiness(
        self,
        server: Server,
        monitoring_target: str | None,
        configs: dict[IntegrationProviderType, ProviderConnectionConfig | None],
        *,
        technical_details: list[str],
    ) -> dict[str, object]:
        prometheus_config = configs.get(IntegrationProviderType.PROMETHEUS)
        loki_config = configs.get(IntegrationProviderType.LOKI)
        strategy = self._monitoring_strategy(server)
        scrape_health = await self._prometheus_target_health(monitoring_target, prometheus_config, technical_details)
        metrics_recent = await self._prometheus_metrics_recent(monitoring_target, prometheus_config, technical_details)
        metrics_available = scrape_health == "up"
        stale_metrics = scrape_health == "up" and not metrics_recent
        logs_available = await self._loki_stream_present(server, monitoring_target, loki_config, technical_details)
        node_exporter_reachable = scrape_health == "up"
        node_exporter_detected = monitoring_target is not None and scrape_health in {"up", "down"}
        promtail_reachable = logs_available
        promtail_detected = logs_available
        docker_runtime_available = self._metadata_bool(server, "docker_runtime_available")
        cadvisor_target = self._container_monitoring_target(server)
        cadvisor_running = await self._prometheus_cadvisor_running(cadvisor_target, prometheus_config, technical_details)
        cadvisor_detected = cadvisor_running or bool(cadvisor_target)

        reasons: list[str] = []
        remediation: list[str] = []
        if not monitoring_target:
            reasons.append("monitoring_target_missing")
            remediation.append("Set a canonical monitoring target such as 100.90.80.15:9100.")
        if not metrics_available:
            reasons.append("metrics_unavailable")
            remediation.append("Verify Prometheus can scrape the configured node_exporter target.")
        if not node_exporter_detected:
            reasons.append("node_exporter_missing")
            remediation.append("Install or start node_exporter for host metrics.")
        elif not node_exporter_reachable:
            reasons.append("node_exporter_unreachable")
        if scrape_health not in {"up", "unknown", "unconfigured"}:
            reasons.append(f"scrape_{scrape_health}")
        if stale_metrics:
            reasons.append("stale_metrics")
            remediation.append("Check Prometheus scrape freshness for the configured target.")
        if not logs_available:
            reasons.append("logs_missing")
            remediation.append("Verify promtail is running and Loki receives logs for this node.")
        if strategy in {"container", "host_container"}:
            if not docker_runtime_available:
                reasons.append("docker_runtime_unavailable")
                remediation.append("Validate Docker runtime before expecting container telemetry.")
            if not cadvisor_running:
                reasons.append("cadvisor_not_running")
                remediation.append("Start cAdvisor as container telemetry; host observability does not require it.")

        if metrics_available and logs_available and not stale_metrics:
            state = "monitoring_ready"
        elif stale_metrics:
            state = "stale_metrics"
        elif metrics_available or logs_available:
            state = "monitoring_partial"
        elif not monitoring_target:
            state = "unknown"
        else:
            state = "monitoring_missing"

        return {
            "monitoring_interface": self._monitoring_interface(server),
            "monitoring_strategy": strategy,
            "metrics_available": metrics_available,
            "logs_available": logs_available,
            "node_exporter_detected": node_exporter_detected,
            "node_exporter_reachable": node_exporter_reachable,
            "cadvisor_detected": cadvisor_detected,
            "cadvisor_running": cadvisor_running,
            "docker_runtime_available": docker_runtime_available,
            "promtail_detected": promtail_detected,
            "promtail_reachable": promtail_reachable,
            "scrape_target_health": scrape_health,
            "stale_metrics": stale_metrics,
            "monitoring_state": state,
            "monitoring_status": self._display_state(state),
            "readiness_reasons": list(dict.fromkeys(reasons)),
            "remediation": list(dict.fromkeys(remediation)),
            "technical_details": technical_details,
        }

    async def _prometheus_target_health(
        self,
        monitoring_target: str | None,
        config: ProviderConnectionConfig | None,
        technical_details: list[str],
    ) -> str:
        if config is None:
            return "unconfigured"
        if not monitoring_target:
            return "unknown"
        try:
            async with httpx.AsyncClient(timeout=config.timeout_seconds, verify=config.verify_ssl) as client:
                response = await client.get(
                    f"{config.base_url}/api/v1/query",
                    params={"query": f'up{{instance="{monitoring_target}"}}'},
                    headers=config.headers,
                )
                response.raise_for_status()
                value = self._first_value(response.json())
                if value == 1:
                    return "up"
                if value == 0:
                    return "down"
        except Exception as exc:
            technical_details.append(f"prometheus_scrape_check: {exc}")
            return "unavailable"
        return "missing"

    async def _prometheus_metrics_recent(
        self,
        monitoring_target: str | None,
        config: ProviderConnectionConfig | None,
        technical_details: list[str],
    ) -> bool:
        if config is None or not monitoring_target:
            return False
        try:
            async with httpx.AsyncClient(timeout=config.timeout_seconds, verify=config.verify_ssl) as client:
                response = await client.get(
                    f"{config.base_url}/api/v1/query",
                    params={"query": f'node_boot_time_seconds{{instance="{monitoring_target}"}}'},
                    headers=config.headers,
                )
                response.raise_for_status()
                sample_time = self._first_timestamp(response.json())
                if sample_time is None:
                    return False
                return (datetime.now(UTC).timestamp() - sample_time) <= 900
        except Exception as exc:
            technical_details.append(f"prometheus_freshness_check: {exc}")
            return False

    async def _prometheus_cadvisor_running(
        self,
        cadvisor_target: str | None,
        config: ProviderConnectionConfig | None,
        technical_details: list[str],
    ) -> bool:
        if config is None or not cadvisor_target:
            return False
        try:
            async with httpx.AsyncClient(timeout=config.timeout_seconds, verify=config.verify_ssl) as client:
                response = await client.get(
                    f"{config.base_url}/api/v1/query",
                    params={"query": f'up{{instance="{cadvisor_target}"}}'},
                    headers=config.headers,
                )
                response.raise_for_status()
                return self._first_value(response.json()) == 1
        except Exception as exc:
            technical_details.append(f"cadvisor_check: {exc}")
            return False

    async def _loki_stream_present(
        self,
        server: Server,
        monitoring_target: str | None,
        config: ProviderConnectionConfig | None,
        technical_details: list[str],
    ) -> bool:
        if config is None:
            return False
        selector = self._loki_selector(server, monitoring_target)
        if selector is None:
            return False
        try:
            async with httpx.AsyncClient(timeout=config.timeout_seconds, verify=config.verify_ssl) as client:
                response = await client.get(
                    f"{config.base_url}/loki/api/v1/query",
                    params={"query": selector},
                    headers=config.headers,
                )
                response.raise_for_status()
                return bool(response.json().get("data", {}).get("result", []))
        except Exception as exc:
            technical_details.append(f"loki_log_check: {exc}")
            return False

    def _static_monitoring_targets(self, server: Server) -> list[str]:
        target = self._monitoring_target(server)
        return [target] if target else []

    @staticmethod
    def _monitoring_interface(server: Server) -> str | None:
        metadata = server.provider_metadata if isinstance(server.provider_metadata, dict) else {}
        value = getattr(server, "monitoring_interface", None) or metadata.get("monitoring_interface")
        return value if isinstance(value, str) and value in {"lan", "tailscale", "localhost", "docker"} else None

    @staticmethod
    def _monitoring_strategy(server: Server) -> str:
        metadata = server.provider_metadata if isinstance(server.provider_metadata, dict) else {}
        value = getattr(server, "monitoring_strategy", None) or metadata.get("monitoring_strategy") or "host"
        return value if isinstance(value, str) and value in {"host", "container", "host_container"} else "host"

    @staticmethod
    def _monitoring_target(server: Server) -> str | None:
        metadata = server.provider_metadata if isinstance(server.provider_metadata, dict) else {}
        value = getattr(server, "monitoring_target", None) or metadata.get("monitoring_target")
        return value.strip() if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _container_monitoring_target(server: Server) -> str | None:
        metadata = server.provider_metadata if isinstance(server.provider_metadata, dict) else {}
        value = metadata.get("cadvisor_target") or metadata.get("container_monitoring_target")
        return value.strip() if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _loki_selector(server: Server, monitoring_target: str | None) -> str | None:
        metadata = server.provider_metadata if isinstance(server.provider_metadata, dict) else {}
        raw_selector = metadata.get("loki_selector")
        if isinstance(raw_selector, str) and raw_selector.strip():
            return raw_selector.strip()
        if monitoring_target:
            return f'{{instance="{monitoring_target}"}}'
        return None

    @staticmethod
    def _operational_summary(server: Server) -> dict[str, float | None]:
        metadata = server.provider_metadata if isinstance(server.provider_metadata, dict) else {}
        return {
            "cpu": _optional_float(metadata.get("cpu_usage_percent")),
            "memory": _optional_float(metadata.get("memory_usage_percent")),
            "disk": _optional_float(metadata.get("disk_usage_percent")),
            "uptime": _optional_float(metadata.get("uptime_seconds")),
        }

    @staticmethod
    def _metadata_bool(server: Server, key: str) -> bool:
        metadata = server.provider_metadata if isinstance(server.provider_metadata, dict) else {}
        return bool(metadata.get(key))

    @staticmethod
    def _display_state(state: str) -> str:
        return {
            "monitoring_ready": "Healthy",
            "monitoring_partial": "Partial",
            "monitoring_missing": "Missing",
            "stale_metrics": "Stale",
            "unknown": "Unknown",
        }.get(state, "Unknown")

    @staticmethod
    def _append_target(targets: list[str], value: object) -> None:
        if isinstance(value, str):
            if value.strip():
                targets.append(value.strip())
            return
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    targets.append(item.strip())
                elif isinstance(item, dict):
                    for key in ("ip", "address", "ip_address", "addr"):
                        nested = item.get(key)
                        if isinstance(nested, str) and nested.strip():
                            targets.append(nested.strip())

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
    def _prometheus_url(config: ProviderConnectionConfig | None, monitoring_targets: list[str]) -> str | None:
        if config is None:
            return None
        if not monitoring_targets:
            return config.base_url
        return f"{config.base_url}/graph?g0.expr=up%7Binstance%3D%22{monitoring_targets[0]}%22%7D"

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


def _optional_float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
