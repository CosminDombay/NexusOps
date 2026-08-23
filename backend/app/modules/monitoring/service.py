import asyncio
from datetime import UTC, datetime, timedelta
from string import Template
from time import perf_counter
from urllib.parse import urlencode
from uuid import UUID

import httpx
import structlog

from backend.app.adapters.ssh import ParamikoSshAdapter, SshAdapter
from backend.app.adapters.ssh.host_keys import HostKeyPolicy
from backend.app.common.constants import InventoryLifecycleState
from backend.app.core.config import settings
from backend.app.modules.audit.repository import AuditEventRepository
from backend.app.modules.audit.service import AuditService
from backend.app.modules.credentials.service import CredentialNotFoundError, CredentialService
from backend.app.modules.integrations.models import IntegrationProviderType
from backend.app.modules.integrations.service import IntegrationService, ProviderConnectionConfig
from backend.app.modules.inventory.models import Server
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.service import ServerNotFoundError
from backend.app.modules.monitoring.models import (
    MonitoringComponentStatus,
    MonitoringSnapshot,
    MonitoringState,
    MonitoringValidationAttempt,
)
from backend.app.modules.monitoring.repository import (
    MonitoringSnapshotRepository,
    MonitoringValidationAttemptRepository,
)
from backend.app.modules.monitoring.schemas import (
    MonitoringOverviewRead,
    MonitoringProviderStatusRead,
    MonitoringValidationRead,
    ServerMetricsRead,
)
from backend.app.modules.runtime_state.repository import (
    NodeRuntimeSnapshotRepository,
    RuntimeRefreshEventRepository,
    RuntimeRefreshStatusRepository,
)
from backend.app.modules.runtime_state.snapshots import RuntimeSnapshotService

logger = structlog.get_logger(__name__)

MONITORING_STALE_AFTER_SECONDS = 900


class MonitoringService:
    """Lightweight monitoring validation backed by persisted snapshots only."""

    def __init__(
        self,
        server_repository: ServerRepository,
        integration_service: IntegrationService,
        snapshot_repository: MonitoringSnapshotRepository | None = None,
        attempt_repository: MonitoringValidationAttemptRepository | None = None,
        audit_service: AuditService | None = None,
        credential_service: CredentialService | None = None,
        ssh_adapter: SshAdapter | None = None,
    ) -> None:
        self.server_repository = server_repository
        self.integration_service = integration_service
        self.snapshot_repository = snapshot_repository or MonitoringSnapshotRepository(
            server_repository.session
        )
        self.attempt_repository = attempt_repository or MonitoringValidationAttemptRepository(server_repository.session)
        self.audit_service = audit_service or AuditService(AuditEventRepository(server_repository.session))
        self.credential_service = credential_service
        self.ssh_adapter = ssh_adapter or ParamikoSshAdapter()
        self.runtime_snapshots = RuntimeSnapshotService(
            NodeRuntimeSnapshotRepository(server_repository.session),
            status_repository=RuntimeRefreshStatusRepository(server_repository.session),
            event_repository=RuntimeRefreshEventRepository(server_repository.session),
        )

    async def overview(self) -> MonitoringOverviewRead:
        servers = await self.server_repository.list()
        snapshots = await self.snapshot_repository.list_by_server_ids(server.id for server in servers)
        providers = await self.snapshot_provider_statuses()
        rows = [self._to_server_read(server, snapshots.get(server.id)) for server in servers]
        return MonitoringOverviewRead(
            total_servers=len(rows),
            online_servers=sum(1 for row in rows if row.online),
            offline_servers=sum(1 for row in rows if not row.online),
            monitored_servers=sum(1 for row in rows if row.monitoring_state == MonitoringState.MONITORED.value),
            partial_servers=sum(1 for row in rows if row.monitoring_state == MonitoringState.PARTIAL.value),
            unmonitored_servers=sum(1 for row in rows if row.monitoring_state == MonitoringState.UNMONITORED.value),
            stale_servers=sum(1 for row in rows if row.monitoring_state == MonitoringState.STALE.value),
            unknown_servers=sum(1 for row in rows if row.monitoring_state == MonitoringState.UNKNOWN.value),
            observable_servers=sum(1 for row in rows if row.monitoring_state == MonitoringState.MONITORED.value),
            degraded_servers=sum(
                1
                for row in rows
                if row.monitoring_state in {MonitoringState.PARTIAL.value, MonitoringState.STALE.value}
            ),
            metrics_missing_servers=sum(1 for row in rows if row.node_exporter_status != "healthy"),
            logs_missing_servers=sum(1 for row in rows if row.promtail_status != "healthy"),
            stale_metrics_servers=sum(1 for row in rows if row.monitoring_state == MonitoringState.STALE.value),
            providers=providers,
            servers=rows,
        )

    async def server_metrics(self, server_id: UUID) -> ServerMetricsRead:
        server = await self.server_repository.get_by_id(server_id)
        if server is None:
            raise ServerNotFoundError("Server not found")
        snapshot = await self.snapshot_repository.get_by_server_id(server.id)
        return self._to_server_read(server, snapshot)

    async def validate_server(self, server_id: UUID) -> MonitoringValidationRead:
        server = await self.server_repository.get_by_id(server_id)
        if server is None:
            raise ServerNotFoundError("Server not found")
        snapshot = await self._validate_server(server)
        await self.snapshot_repository.session.commit()
        await self.snapshot_repository.session.refresh(snapshot)
        return MonitoringValidationRead(
            checked_servers=1,
            updated_servers=1,
            failed_servers=1 if snapshot.last_error else 0,
        )

    async def validate_all(self) -> MonitoringValidationRead:
        servers = await self.server_repository.list()
        checked = updated = failed = 0
        for server in servers:
            checked += 1
            try:
                snapshot = await self._validate_server(server)
                updated += 1
                if snapshot.last_error:
                    failed += 1
            except Exception as exc:
                failed += 1
                logger.warning("monitoring_validation_failed", server_id=str(server.id), reason=str(exc))
        await self.runtime_snapshots.record_refresh_status(
            "monitoring",
            "failed" if failed and failed == checked else "success",
            error="all monitoring validations failed" if failed and failed == checked else None,
            metadata_json={"checked_servers": checked, "updated_servers": updated, "failed_servers": failed},
            commit=False,
        )
        await self.snapshot_repository.session.commit()
        return MonitoringValidationRead(
            checked_servers=checked,
            updated_servers=updated,
            failed_servers=failed,
        )

    async def snapshot_provider_statuses(self) -> list[MonitoringProviderStatusRead]:
        configs = await self._provider_configs()
        latest_snapshot = await self.snapshot_repository.latest_validated()
        prometheus_config = configs.get(IntegrationProviderType.PROMETHEUS)
        grafana_config = configs.get(IntegrationProviderType.GRAFANA)
        prometheus_reachable = (
            latest_snapshot is not None
            and latest_snapshot.prometheus_target_health == MonitoringComponentStatus.HEALTHY
        )
        prometheus_error = None
        if prometheus_config is None:
            prometheus_error = "prometheus integration is not configured or is disabled"
        elif latest_snapshot is None:
            prometheus_error = "monitoring validation has not run"
        elif not prometheus_reachable:
            prometheus_error = "prometheus health check is unavailable"
        return [
            MonitoringProviderStatusRead(
                provider_type=IntegrationProviderType.PROMETHEUS.value,
                configured=prometheus_config is not None,
                reachable=prometheus_reachable,
                integration_id=prometheus_config.integration_id if prometheus_config else None,
                url=prometheus_config.base_url if prometheus_config else None,
                error=prometheus_error,
            ),
            MonitoringProviderStatusRead(
                provider_type=IntegrationProviderType.GRAFANA.value,
                configured=grafana_config is not None,
                reachable=grafana_config is not None,
                integration_id=grafana_config.integration_id if grafana_config else None,
                url=grafana_config.base_url if grafana_config else None,
                error=None if grafana_config else "grafana integration is not configured or is disabled",
            ),
        ]

    async def _validate_server(self, server: Server) -> MonitoringSnapshot:
        started_at = datetime.now(UTC)
        started_timer = perf_counter()
        now = started_at
        configs = await self._provider_configs()
        prometheus_config = configs.get(IntegrationProviderType.PROMETHEUS)
        grafana_config = configs.get(IntegrationProviderType.GRAFANA)
        target_host = self._target_host(server)
        monitoring_target = self._monitoring_target(server, target_host)

        if not self._is_monitorable(server):
            snapshot = MonitoringSnapshot(
                server_id=server.id,
                integration_id=prometheus_config.integration_id if prometheus_config else None,
                monitoring_state=MonitoringState.UNMONITORED,
                node_exporter_status=MonitoringComponentStatus.NOT_CONFIGURED,
                promtail_status=MonitoringComponentStatus.NOT_CONFIGURED,
                cadvisor_status=MonitoringComponentStatus.NOT_CONFIGURED,
                prometheus_target_health=MonitoringComponentStatus.NOT_CONFIGURED,
                monitoring_target=monitoring_target,
                grafana_url=self._grafana_url(grafana_config, server, monitoring_target),
                last_validated_at=now,
                last_successful_check_at=None,
                stale_after=now + timedelta(seconds=MONITORING_STALE_AFTER_SECONDS),
                last_error="node is not managed or active",
                details={"reason": "node_not_monitorable"},
            )
            saved = await self._save_snapshot(server, snapshot)
            await self._record_validation_attempt(
                server,
                saved,
                started_at=started_at,
                started_timer=started_timer,
                component_results={},
                validation_method="not_monitorable",
                result="skipped",
                failure_reason="node_not_monitorable",
            )
            return saved

        prometheus_status, prometheus_reason = await self._http_health(prometheus_config, "/-/healthy")
        node_status, node_method, node_reason = await self._component_status(
            server,
            target_host,
            port=self._port(server, "node_exporter_port", 9100),
            services=("node_exporter", "node-exporter"),
        )
        promtail_status, promtail_method, promtail_reason = await self._component_status(
            server,
            target_host,
            port=self._port(server, "promtail_port", 9080),
            services=("promtail",),
        )
        cadvisor_status, cadvisor_method, cadvisor_reason = await self._component_status(
            server,
            target_host,
            port=self._port(server, "cadvisor_port", 8080),
            services=("cadvisor", "cAdvisor"),
            docker_pattern="cadvisor",
        )
        prometheus_target_health = prometheus_status
        component_statuses = [node_status, promtail_status, cadvisor_status]
        state = self._rollup_state(component_statuses)
        last_successful = now if state in {MonitoringState.MONITORED, MonitoringState.PARTIAL} else None
        previous = await self.snapshot_repository.get_by_server_id(server.id)
        if last_successful is None and previous is not None:
            last_successful = previous.last_successful_check_at

        snapshot = MonitoringSnapshot(
            server_id=server.id,
            integration_id=prometheus_config.integration_id if prometheus_config else None,
            monitoring_state=state,
            node_exporter_status=node_status,
            promtail_status=promtail_status,
            cadvisor_status=cadvisor_status,
            prometheus_target_health=prometheus_target_health,
            monitoring_target=monitoring_target,
            grafana_url=self._grafana_url(grafana_config, server, monitoring_target),
            last_validated_at=now,
            last_successful_check_at=last_successful,
            stale_after=now + timedelta(seconds=MONITORING_STALE_AFTER_SECONDS),
            last_error=self._snapshot_error(state, prometheus_status),
            details={
                "validation_method": "tcp_http_reachability",
                "target_host": target_host,
                "ports": {
                    "node_exporter": self._port(server, "node_exporter_port", 9100),
                    "promtail": self._port(server, "promtail_port", 9080),
                    "cadvisor": self._port(server, "cadvisor_port", 8080),
                },
                "validation_methods": {
                    "node_exporter": node_method,
                    "promtail": promtail_method,
                    "cadvisor": cadvisor_method,
                },
                "prometheus_reachable": prometheus_status == MonitoringComponentStatus.HEALTHY,
                "failure_reasons": {
                    "node_exporter": node_reason,
                    "promtail": promtail_reason,
                    "cadvisor": cadvisor_reason,
                    "prometheus": prometheus_reason,
                },
            },
        )
        saved = await self._save_snapshot(server, snapshot)
        component_results = {
            "node_exporter": {"status": node_status.value, "method": node_method, "failure_reason": node_reason},
            "promtail": {"status": promtail_status.value, "method": promtail_method, "failure_reason": promtail_reason},
            "cadvisor": {"status": cadvisor_status.value, "method": cadvisor_method, "failure_reason": cadvisor_reason},
            "prometheus": {"status": prometheus_status.value, "method": "http_health", "failure_reason": prometheus_reason},
        }
        await self._record_validation_attempt(
            server,
            saved,
            started_at=started_at,
            started_timer=started_timer,
            component_results=component_results,
            validation_method="tcp_http_ssh",
            result="success" if state in {MonitoringState.MONITORED, MonitoringState.PARTIAL} else "failed",
            failure_reason=self._primary_failure_reason(component_results),
        )
        return saved

    async def _save_snapshot(self, server: Server, snapshot: MonitoringSnapshot) -> MonitoringSnapshot:
        saved = await self.snapshot_repository.upsert(snapshot)
        await self.runtime_snapshots.refresh_monitoring_snapshot(
            server,
            monitoring_targets=[snapshot.monitoring_target] if snapshot.monitoring_target else [],
            metrics={},
            observability={
                "monitoring_state": self._runtime_monitoring_state(snapshot.monitoring_state),
                "node_exporter_reachable": snapshot.node_exporter_status == MonitoringComponentStatus.HEALTHY,
                "promtail_reachable": snapshot.promtail_status == MonitoringComponentStatus.HEALTHY,
                "cadvisor_running": snapshot.cadvisor_status == MonitoringComponentStatus.HEALTHY,
                "scrape_target_health": snapshot.prometheus_target_health.value,
                "stale_metrics": snapshot.monitoring_state == MonitoringState.STALE,
            },
            metrics_error=snapshot.last_error,
            commit=False,
        )
        return saved

    async def _provider_configs(self) -> dict[IntegrationProviderType, ProviderConnectionConfig | None]:
        return {
            provider_type: await self.integration_service.get_provider_connection_config(
                provider_type,
                default_timeout_seconds=settings.monitoring_timeout_seconds,
            )
            for provider_type in (IntegrationProviderType.PROMETHEUS, IntegrationProviderType.GRAFANA)
        }

    async def _http_health(
        self,
        config: ProviderConnectionConfig | None,
        path: str,
    ) -> tuple[MonitoringComponentStatus, str | None]:
        if config is None:
            return MonitoringComponentStatus.NOT_CONFIGURED, "provider_not_configured"
        try:
            async with httpx.AsyncClient(timeout=config.timeout_seconds, verify=config.verify_ssl) as client:
                response = await client.get(f"{config.base_url}{path}", headers=config.headers)
                response.raise_for_status()
        except TimeoutError:
            return MonitoringComponentStatus.UNAVAILABLE, "command_timeout"
        except Exception:
            return MonitoringComponentStatus.UNAVAILABLE, "provider_unreachable"
        return MonitoringComponentStatus.HEALTHY, None

    async def _tcp_status(self, host: str | None, port: int | None) -> tuple[MonitoringComponentStatus, str | None]:
        if not host or not port:
            return MonitoringComponentStatus.NOT_CONFIGURED, "target_not_configured"
        try:
            _reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=settings.monitoring_timeout_seconds,
            )
            writer.close()
            await writer.wait_closed()
        except TimeoutError:
            return MonitoringComponentStatus.UNAVAILABLE, "tcp_unreachable"
        except Exception:
            return MonitoringComponentStatus.UNAVAILABLE, "tcp_unreachable"
        return MonitoringComponentStatus.HEALTHY, None

    async def _component_status(
        self,
        server: Server,
        host: str | None,
        *,
        port: int,
        services: tuple[str, ...],
        docker_pattern: str | None = None,
    ) -> tuple[MonitoringComponentStatus, str, str | None]:
        tcp_status, tcp_reason = await self._tcp_status(host, port)
        if tcp_status == MonitoringComponentStatus.HEALTHY:
            return tcp_status, "tcp", None
        systemd_status, systemd_reason = await self._systemctl_status(server, services)
        if systemd_status == MonitoringComponentStatus.HEALTHY:
            return systemd_status, "ssh_systemctl", None
        if docker_pattern:
            docker_status, docker_reason = await self._docker_container_status(server, docker_pattern)
            if docker_status == MonitoringComponentStatus.HEALTHY:
                return docker_status, "ssh_docker_ps", None
            if systemd_status == MonitoringComponentStatus.NOT_CONFIGURED:
                return docker_status, "ssh_docker_ps", docker_reason
        if systemd_status == MonitoringComponentStatus.NOT_CONFIGURED:
            return tcp_status, "tcp", tcp_reason
        return systemd_status, "ssh_systemctl", systemd_reason

    async def _systemctl_status(
        self,
        server: Server,
        services: tuple[str, ...],
    ) -> tuple[MonitoringComponentStatus, str | None]:
        if not server.ssh_username and server.credential_id is None:
            return MonitoringComponentStatus.NOT_CONFIGURED, "ssh_not_configured"
        service_checks = " ".join(self._sh_quote(service) for service in services)
        command = (
            "for svc in "
            f"{service_checks}; do "
            "systemctl is-active --quiet \"$svc\" && exit 0; "
            "done; exit 3"
        )
        try:
            details = await self._ssh_details(server)
            host_key_policy = HostKeyPolicy.for_server(server)
            result = await self.ssh_adapter.run_command(
                host=server.ip_address,
                port=server.ssh_port,
                command=command,
                user=details["user"],
                password=details["password"],
                private_key_path=details["private_key_path"],
                private_key=details["private_key"],
                passphrase=details["passphrase"],
                host_key_policy=host_key_policy,
            )
            host_key_policy.persist_to(server)
        except CredentialNotFoundError:
            return MonitoringComponentStatus.UNAVAILABLE, "ssh_auth_failed"
        except TimeoutError:
            return MonitoringComponentStatus.UNAVAILABLE, "command_timeout"
        except Exception:
            return MonitoringComponentStatus.UNAVAILABLE, "ssh_auth_failed"
        if result.exit_code == 0:
            return MonitoringComponentStatus.HEALTHY, None
        return MonitoringComponentStatus.UNAVAILABLE, "service_inactive"

    async def _docker_container_status(
        self,
        server: Server,
        pattern: str,
    ) -> tuple[MonitoringComponentStatus, str | None]:
        command = (
            "docker ps --format '{{.Names}} {{.Image}}' "
            f"| grep -i -- {self._sh_quote(pattern)} >/dev/null"
        )
        try:
            details = await self._ssh_details(server)
            host_key_policy = HostKeyPolicy.for_server(server)
            result = await self.ssh_adapter.run_command(
                host=server.ip_address,
                port=server.ssh_port,
                command=command,
                user=details["user"],
                password=details["password"],
                private_key_path=details["private_key_path"],
                private_key=details["private_key"],
                passphrase=details["passphrase"],
                host_key_policy=host_key_policy,
            )
            host_key_policy.persist_to(server)
        except CredentialNotFoundError:
            return MonitoringComponentStatus.UNAVAILABLE, "ssh_auth_failed"
        except TimeoutError:
            return MonitoringComponentStatus.UNAVAILABLE, "command_timeout"
        except Exception:
            return MonitoringComponentStatus.UNAVAILABLE, "docker_unavailable"
        if result.exit_code == 0:
            return MonitoringComponentStatus.HEALTHY, None
        return MonitoringComponentStatus.UNAVAILABLE, "exporter_missing"

    async def _ssh_details(self, server: Server) -> dict[str, str | None | int]:
        from backend.app.modules.inventory.models import ServerSshAuthMethod

        ssh_user = server.ssh_username
        ssh_password = server.ssh_password if server.ssh_auth_method == ServerSshAuthMethod.PASSWORD else None
        ssh_private_key_path = (
            server.ssh_private_key_path if server.ssh_auth_method == ServerSshAuthMethod.KEY else None
        )
        ssh_private_key: str | None = None
        ssh_passphrase: str | None = None
        if server.credential_id is not None:
            if self.credential_service is None:
                raise CredentialNotFoundError("Credential service is required for credential-backed monitoring validation")
            credential = await self.credential_service.resolve_credential(server.credential_id)
            ssh_user = credential.username or ssh_user
            if credential.credential_type in {"password", "ssh_password"}:
                ssh_password = credential.secret
                ssh_private_key_path = None
            elif credential.credential_type == "ssh_key":
                ssh_password = None
                ssh_private_key_path = None
                ssh_private_key = credential.private_key
                ssh_passphrase = credential.passphrase
        return {
            "user": ssh_user,
            "password": ssh_password,
            "private_key_path": ssh_private_key_path,
            "private_key": ssh_private_key,
            "passphrase": ssh_passphrase,
        }

    def _to_server_read(self, server: Server, snapshot: MonitoringSnapshot | None) -> ServerMetricsRead:
        snapshot = self._mark_stale(snapshot)
        monitoring_target = snapshot.monitoring_target if snapshot else self._monitoring_target(server, self._target_host(server))
        node_exporter = self._status_value(snapshot.node_exporter_status if snapshot else None)
        promtail = self._status_value(snapshot.promtail_status if snapshot else None)
        cadvisor = self._status_value(snapshot.cadvisor_status if snapshot else None)
        prometheus = self._status_value(snapshot.prometheus_target_health if snapshot else None)
        state = self._state_value(snapshot.monitoring_state if snapshot else None)
        return ServerMetricsRead(
            server_id=server.id,
            hostname=server.hostname,
            ip_address=server.ip_address,
            monitoring_targets=[monitoring_target] if monitoring_target else [],
            monitoring_interface=server.monitoring_interface,
            monitoring_strategy=server.monitoring_strategy or "host",
            online=self._is_monitorable(server),
            grafana_url=snapshot.grafana_url if snapshot else None,
            open_grafana_url=snapshot.grafana_url if snapshot else None,
            monitoring_state=state,
            monitoring_status=self._display_state(state),
            node_exporter_status=node_exporter,
            promtail_status=promtail,
            cadvisor_status=cadvisor,
            prometheus_target_health=prometheus,
            node_exporter_detected=node_exporter == "healthy",
            node_exporter_reachable=node_exporter == "healthy",
            cadvisor_detected=cadvisor == "healthy",
            cadvisor_running=cadvisor == "healthy",
            promtail_detected=promtail == "healthy",
            promtail_reachable=promtail == "healthy",
            scrape_target_health=prometheus,
            metrics_available=node_exporter == "healthy",
            logs_available=promtail == "healthy",
            stale_metrics=state == MonitoringState.STALE.value,
            readiness_reasons=self._readiness_reasons(snapshot),
            technical_details=self._technical_details(snapshot),
            component_failure_reasons=self._component_failure_reasons(snapshot),
            last_validated_at=snapshot.last_validated_at if snapshot else None,
            last_successful_check_at=snapshot.last_successful_check_at if snapshot else None,
            collected_at=snapshot.last_validated_at if snapshot and snapshot.last_validated_at else datetime.now(UTC),
        )

    @staticmethod
    def _rollup_state(
        component_statuses: list[MonitoringComponentStatus],
    ) -> MonitoringState:
        healthy_count = sum(1 for status in component_statuses if status == MonitoringComponentStatus.HEALTHY)
        if healthy_count == len(component_statuses):
            return MonitoringState.MONITORED
        if healthy_count:
            return MonitoringState.PARTIAL
        if any(status == MonitoringComponentStatus.UNAVAILABLE for status in component_statuses):
            return MonitoringState.UNMONITORED
        return MonitoringState.UNKNOWN

    @staticmethod
    def _mark_stale(snapshot: MonitoringSnapshot | None) -> MonitoringSnapshot | None:
        if snapshot is None or snapshot.monitoring_state == MonitoringState.STALE:
            return snapshot
        stale_after = snapshot.stale_after
        if stale_after and stale_after.tzinfo is None:
            stale_after = stale_after.replace(tzinfo=UTC)
        if stale_after and stale_after < datetime.now(UTC):
            snapshot.monitoring_state = MonitoringState.STALE
        return snapshot

    @staticmethod
    def _is_monitorable(server: Server) -> bool:
        return bool(
            server.managed
            and server.lifecycle_state
            not in {
                InventoryLifecycleState.ARCHIVED,
                InventoryLifecycleState.DECOMMISSIONED,
                InventoryLifecycleState.DELETED,
            }
        )

    @staticmethod
    def _target_host(server: Server) -> str | None:
        metadata = server.provider_metadata if isinstance(server.provider_metadata, dict) else {}
        value = server.monitoring_target or metadata.get("monitoring_target") or server.ip_address
        if not isinstance(value, str) or not value.strip():
            return None
        host = value.strip()
        if host.startswith("[") and "]" in host:
            return host[1 : host.index("]")]
        return host.rsplit(":", 1)[0] if ":" in host else host

    @staticmethod
    def _monitoring_target(server: Server, target_host: str | None) -> str | None:
        metadata = server.provider_metadata if isinstance(server.provider_metadata, dict) else {}
        value = server.monitoring_target or metadata.get("monitoring_target")
        if isinstance(value, str) and value.strip():
            return value.strip()
        return f"{target_host}:9100" if target_host else None

    @staticmethod
    def _port(server: Server, key: str, default: int) -> int:
        metadata = server.provider_metadata if isinstance(server.provider_metadata, dict) else {}
        value = metadata.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return default
        return default

    @staticmethod
    def _grafana_url(
        config: ProviderConnectionConfig | None,
        server: Server,
        monitoring_target: str | None,
    ) -> str | None:
        if config is None:
            return None
        raw_config = config.raw_config or {}
        metadata = server.provider_metadata if isinstance(server.provider_metadata, dict) else {}
        variables = {
            "hostname": server.hostname,
            "node": server.hostname,
            "ip_address": server.ip_address,
            "instance": monitoring_target or "",
            "provider": server.provider,
            "provider_node": server.provider_node or "",
            **{key: str(value) for key, value in metadata.items() if isinstance(value, str | int | float)},
        }
        explicit = metadata.get("grafana_url") or metadata.get("grafana_dashboard_url")
        if isinstance(explicit, str) and explicit.strip():
            return Template(explicit.strip()).safe_substitute(variables)
        path_template = raw_config.get("dashboard_path_template") or raw_config.get("dashboard_path")
        uid_template = raw_config.get("dashboard_uid_template") or raw_config.get("dashboard_uid")
        slug_template = raw_config.get("dashboard_slug_template") or raw_config.get("dashboard_slug") or "node"
        if isinstance(path_template, str) and path_template.strip():
            path = Template(path_template.strip()).safe_substitute(variables)
        elif isinstance(uid_template, str) and uid_template.strip():
            uid = Template(uid_template.strip()).safe_substitute(variables)
            slug = Template(str(slug_template)).safe_substitute(variables)
            path = f"/d/{uid}/{slug}"
        else:
            path = str(raw_config.get("default_dashboard_path") or "/").strip()
        path = path if path.startswith("/") else f"/{path}"
        query = {
            "orgId": raw_config.get("org_id") or raw_config.get("grafana_org_id") or "1",
            "var-hostname": server.hostname,
            "var-node": server.hostname,
            "var-instance": monitoring_target or "",
        }
        return f"{config.base_url}{path}?{urlencode({k: v for k, v in query.items() if v})}"

    @staticmethod
    def _runtime_monitoring_state(state: MonitoringState) -> str:
        return {
            MonitoringState.MONITORED: "monitoring_ready",
            MonitoringState.PARTIAL: "monitoring_partial",
            MonitoringState.UNMONITORED: "monitoring_missing",
            MonitoringState.STALE: "stale_metrics",
            MonitoringState.UNKNOWN: "unknown",
        }[state]

    @staticmethod
    def _display_state(state: str) -> str:
        return {
            MonitoringState.MONITORED.value: "Monitored",
            MonitoringState.PARTIAL.value: "Partial",
            MonitoringState.UNMONITORED.value: "Unmonitored",
            MonitoringState.STALE.value: "Stale",
            MonitoringState.UNKNOWN.value: "Unknown",
        }.get(state, "Unknown")

    @staticmethod
    def _state_value(value: MonitoringState | None) -> str:
        return value.value if isinstance(value, MonitoringState) else MonitoringState.UNKNOWN.value

    @staticmethod
    def _status_value(value: MonitoringComponentStatus | None) -> str:
        return value.value if isinstance(value, MonitoringComponentStatus) else MonitoringComponentStatus.UNKNOWN.value

    @staticmethod
    def _snapshot_error(state: MonitoringState, prometheus_status: MonitoringComponentStatus) -> str | None:
        if state in {MonitoringState.MONITORED, MonitoringState.PARTIAL}:
            return None
        if prometheus_status == MonitoringComponentStatus.UNAVAILABLE:
            return "monitoring infrastructure unavailable"
        return "monitoring exporters unavailable"

    @staticmethod
    def _readiness_reasons(snapshot: MonitoringSnapshot | None) -> list[str]:
        if snapshot is None:
            return ["monitoring snapshot has not been validated"]
        reasons = []
        for label, status in (
            ("node_exporter", snapshot.node_exporter_status),
            ("promtail", snapshot.promtail_status),
            ("cadvisor", snapshot.cadvisor_status),
        ):
            if status != MonitoringComponentStatus.HEALTHY:
                reasons.append(f"{label}_{status.value}")
        if snapshot.monitoring_state == MonitoringState.STALE:
            reasons.append("monitoring_snapshot_stale")
        return reasons

    @staticmethod
    def _component_failure_reasons(snapshot: MonitoringSnapshot | None) -> dict[str, str]:
        if snapshot is None or not isinstance(snapshot.details, dict):
            return {}
        raw_reasons = snapshot.details.get("failure_reasons")
        if not isinstance(raw_reasons, dict):
            return {}
        return {
            str(component): str(reason)
            for component, reason in raw_reasons.items()
            if reason is not None
        }

    @staticmethod
    def _primary_failure_reason(component_results: dict[str, object]) -> str | None:
        priority = (
            "ssh_auth_failed",
            "command_timeout",
            "tcp_unreachable",
            "service_inactive",
            "docker_unavailable",
            "exporter_missing",
            "provider_unreachable",
            "provider_not_configured",
            "target_not_configured",
            "ssh_not_configured",
        )
        reasons = []
        for value in component_results.values():
            if isinstance(value, dict) and value.get("failure_reason"):
                reasons.append(str(value["failure_reason"]))
        for item in priority:
            if item in reasons:
                return item
        return reasons[0] if reasons else None

    async def _record_validation_attempt(
        self,
        server: Server,
        snapshot: MonitoringSnapshot,
        *,
        started_at: datetime,
        started_timer: float,
        component_results: dict[str, object],
        validation_method: str,
        result: str,
        failure_reason: str | None,
    ) -> None:
        finished_at = datetime.now(UTC)
        duration_ms = max(0, int((perf_counter() - started_timer) * 1000))
        audit_event = await self.audit_service.record(
            event_type="monitoring.validation",
            target_type="server",
            target_id=server.id,
            result=result,
            metadata={
                "hostname": server.hostname,
                "monitoring_state": snapshot.monitoring_state.value,
                "validation_method": validation_method,
                "failure_reason": failure_reason,
                "component_results": component_results,
                "duration_ms": duration_ms,
            },
            error=failure_reason if result == "failed" else None,
            commit=False,
        )
        attempt = MonitoringValidationAttempt(
            server_id=server.id,
            monitoring_snapshot_id=snapshot.id,
            audit_event_id=audit_event.id if audit_event is not None else None,
            validation_method=validation_method,
            component_results=component_results,
            monitoring_state=snapshot.monitoring_state,
            result=result,
            failure_reason=failure_reason,
            duration_ms=duration_ms,
            started_at=started_at,
            finished_at=finished_at,
            details={
                "monitoring_target": snapshot.monitoring_target,
                "grafana_url": snapshot.grafana_url,
            },
        )
        await self.attempt_repository.create(attempt)

    @staticmethod
    def _technical_details(snapshot: MonitoringSnapshot | None) -> list[str]:
        if snapshot is None:
            return []
        details = snapshot.details if isinstance(snapshot.details, dict) else {}
        values = []
        if snapshot.last_error:
            values.append(snapshot.last_error)
        target_host = details.get("target_host")
        if target_host:
            values.append(f"target_host={target_host}")
        return values

    @staticmethod
    def _sh_quote(value: str) -> str:
        return "'" + value.replace("'", "'\"'\"'") + "'"
