from datetime import UTC, datetime, timedelta
from uuid import UUID

from backend.app.modules.inventory.models import Server
from backend.app.modules.runtime_state.models import (
    NodeRuntimeSnapshot,
    RuntimeRefreshEvent,
    RuntimeRefreshStatus,
)
from backend.app.modules.runtime_state.repository import (
    NodeRuntimeSnapshotRepository,
    RuntimeRefreshEventRepository,
    RuntimeRefreshStatusRepository,
)
from backend.app.modules.runtime_state.schemas import (
    NodeRuntimeEligibility,
    NodeRuntimeFreshness,
    NodeRuntimeReconciliation,
    NodeRuntimeState,
    RuntimeRefreshStatusRead,
)
from backend.app.modules.runtime_state.service import RuntimeStateService

DEFAULT_STALE_AFTER_SECONDS = 300


class RuntimeSnapshotService:
    """Persists and reads node runtime snapshots without live infrastructure calls."""

    def __init__(
        self,
        snapshot_repository: NodeRuntimeSnapshotRepository,
        status_repository: RuntimeRefreshStatusRepository | None = None,
        event_repository: RuntimeRefreshEventRepository | None = None,
    ) -> None:
        self.snapshot_repository = snapshot_repository
        self.status_repository = status_repository
        self.event_repository = event_repository

    async def attach_snapshots(self, servers: list[Server]) -> list[Server]:
        snapshots = await self.snapshot_repository.list_by_node_ids(server.id for server in servers)
        for server in servers:
            snapshot = snapshots.get(server.id)
            if snapshot is None:
                continue
            setattr(server, "runtime_state", self.to_runtime_state(snapshot))
        return servers

    async def attach_snapshot(self, server: Server) -> Server:
        await self.attach_snapshots([server])
        return server

    async def refresh_inventory_snapshot(
        self,
        server: Server,
        *,
        commit: bool = True,
        monitoring_targets: list[str] | None = None,
        metrics: dict[str, object] | None = None,
        observability: dict[str, object] | None = None,
        last_error: str | None = None,
        stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    ) -> NodeRuntimeSnapshot:
        now = datetime.now(UTC)
        runtime_state = RuntimeStateService.from_inventory_node(server)
        snapshot = self._from_runtime_state(
            server.id,
            runtime_state,
            now=now,
            stale_after=now + timedelta(seconds=stale_after_seconds),
            refresh_scope="inventory",
            refresh_status="failed" if last_error else "success",
            last_error=last_error,
            monitoring_targets=monitoring_targets,
            metrics=metrics,
            observability=observability,
        )
        saved = await self.snapshot_repository.upsert(snapshot)
        setattr(server, "runtime_state", self.to_runtime_state(saved))
        if commit:
            await self.snapshot_repository.session.commit()
            await self.snapshot_repository.session.refresh(saved)
        return saved

    async def refresh_monitoring_snapshot(
        self,
        server: Server,
        *,
        monitoring_targets: list[str],
        metrics: dict[str, object],
        observability: dict[str, object],
        metrics_error: str | None = None,
        commit: bool = True,
    ) -> NodeRuntimeSnapshot:
        now = datetime.now(UTC)
        runtime_state = RuntimeStateService.from_inventory_node(server)
        monitoring_state = observability.get("monitoring_state")
        if isinstance(monitoring_state, str) and monitoring_state:
            runtime_state.monitoring_state = monitoring_state
        runtime_state.readiness_state = RuntimeStateService._readiness_state(
            ssh_state=runtime_state.ssh_state,
            monitoring_state=runtime_state.monitoring_state,
            orchestration_state=runtime_state.orchestration_state,
        )
        runtime_state.degraded_reasons = list(
            dict.fromkeys(
                [
                    *runtime_state.degraded_reasons,
                    *(
                        [runtime_state.monitoring_state]
                        if runtime_state.monitoring_state
                        in {"monitoring_missing", "monitoring_partial", "stale_metrics"}
                        else []
                    ),
                ]
            )
        )
        snapshot = self._from_runtime_state(
            server.id,
            runtime_state,
            now=now,
            stale_after=now + timedelta(seconds=DEFAULT_STALE_AFTER_SECONDS),
            refresh_scope="monitoring",
            refresh_status="failed" if metrics_error else "success",
            last_error=metrics_error,
            monitoring_targets=monitoring_targets,
            metrics=metrics,
            observability=observability,
        )
        saved = await self.snapshot_repository.upsert(snapshot)
        setattr(server, "runtime_state", self.to_runtime_state(saved))
        if commit:
            await self.record_refresh_status(
                "monitoring",
                "failed" if metrics_error else "success",
                error=metrics_error,
                metadata_json={"node_id": str(server.id), "hostname": server.hostname},
                node_id=server.id,
                commit=False,
            )
            await self.snapshot_repository.session.commit()
            await self.snapshot_repository.session.refresh(saved)
        return saved

    async def refresh_provider_snapshot(
        self,
        server: Server,
        *,
        provider_state: str,
        provider_reachable: bool,
        provider_guest_exists: bool,
        commit: bool = True,
    ) -> NodeRuntimeSnapshot:
        now = datetime.now(UTC)
        runtime_state = RuntimeStateService.from_inventory_node(
            server,
            provider_state=provider_state,
            provider_reachable=provider_reachable,
            provider_guest_exists=provider_guest_exists,
        )
        snapshot = self._from_runtime_state(
            server.id,
            runtime_state,
            now=now,
            stale_after=now + timedelta(seconds=DEFAULT_STALE_AFTER_SECONDS),
            refresh_scope="provider",
            refresh_status="success",
        )
        saved = await self.snapshot_repository.upsert(snapshot)
        setattr(server, "runtime_state", self.to_runtime_state(saved))
        if commit:
            await self.record_refresh_status(
                "provider",
                "success",
                metadata_json={"node_id": str(server.id), "hostname": server.hostname},
                node_id=server.id,
                commit=False,
            )
            await self.snapshot_repository.session.commit()
            await self.snapshot_repository.session.refresh(saved)
        return saved

    async def refresh_inventory_snapshots(
        self,
        servers: list[Server],
        *,
        commit: bool = True,
    ) -> list[NodeRuntimeSnapshot]:
        snapshots = [
            await self.refresh_inventory_snapshot(server, commit=False)
            for server in servers
        ]
        if self.status_repository is not None:
            await self.record_refresh_status(
                "inventory",
                "success",
                metadata_json={"node_count": len(snapshots)},
                commit=False,
            )
        if commit:
            await self.snapshot_repository.session.commit()
        return snapshots

    async def record_refresh_status(
        self,
        scope: str,
        status: str,
        *,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        error: str | None = None,
        metadata_json: dict[str, object] | None = None,
        node_id: UUID | None = None,
        commit: bool = True,
    ) -> RuntimeRefreshStatus | None:
        now = datetime.now(UTC)
        started_at = started_at or now
        finished_at = finished_at or now
        if self.event_repository is not None:
            await self.event_repository.create(
                RuntimeRefreshEvent(
                    scope=scope,
                    node_id=node_id,
                    status=status,
                    started_at=started_at,
                    finished_at=finished_at,
                    error=error,
                    metadata_json=metadata_json or {},
                )
            )
        saved_status = None
        if self.status_repository is not None:
            saved_status = await self.status_repository.upsert(
                RuntimeRefreshStatus(
                    scope=scope,
                    status=status,
                    started_at=started_at,
                    finished_at=finished_at,
                    last_error=error,
                    metadata_json=metadata_json or {},
                )
            )
        if commit:
            await self.snapshot_repository.session.commit()
        return saved_status

    async def list_refresh_statuses(self) -> list[RuntimeRefreshStatusRead]:
        if self.status_repository is None:
            return []
        return [
            RuntimeRefreshStatusRead(
                scope=status.scope,
                status=status.status,
                started_at=status.started_at,
                finished_at=status.finished_at,
                last_error=status.last_error,
                metadata_json=status.metadata_json,
            )
            for status in await self.status_repository.list()
        ]

    @staticmethod
    def to_runtime_state(snapshot: NodeRuntimeSnapshot) -> NodeRuntimeState:
        administrative_state = snapshot.lifecycle_state
        if administrative_state not in {"archived", "decommissioned", "deleted"}:
            administrative_state = "active"
        infrastructure_state = "missing" if not snapshot.provider_guest_exists and snapshot.provider_state != "not_provider_backed" else snapshot.provider_state
        if infrastructure_state not in {"running", "stopped", "missing"}:
            infrastructure_state = "unknown"
        observability_state = snapshot.monitoring_state if snapshot.monitoring_state in {"monitoring_ready", "monitoring_partial", "stale_metrics"} else "missing"
        return NodeRuntimeState(
            administrative_state=administrative_state,
            infrastructure_state=infrastructure_state,
            observability_state=observability_state,
            inventory_state=snapshot.lifecycle_state,
            provider_state=snapshot.provider_state,
            provider_reachable=snapshot.provider_reachable,
            provider_guest_exists=snapshot.provider_guest_exists,
            ssh_state=snapshot.ssh_state,
            monitoring_state=snapshot.monitoring_state,
            readiness_state=snapshot.readiness_state,
            orchestration_state=snapshot.orchestration_state,
            lifecycle_state=snapshot.lifecycle_state,
            eligibility=NodeRuntimeEligibility.model_validate(snapshot.eligibility or {}),
            reconciliation=NodeRuntimeReconciliation(
                provider_link_status="linked" if snapshot.provider_guest_exists else "provider_guest_missing",
                confidence="low" if snapshot.stale_reasons else "medium",
                drift_indicators=list(snapshot.stale_reasons or []),
                provider_sync_freshness="stale" if snapshot.stale_reasons else "fresh",
            ),
            freshness=NodeRuntimeFreshness(
                monitoring_refreshed_at=snapshot.last_checked_at if snapshot.refresh_scope == "monitoring" else None,
                provider_refreshed_at=snapshot.last_checked_at if snapshot.refresh_scope == "provider" else None,
                inventory_refreshed_at=snapshot.last_checked_at if snapshot.refresh_scope == "inventory" else None,
                runtime_refreshed_at=snapshot.last_checked_at,
                confidence="low" if snapshot.stale_reasons else "medium",
            ),
            degraded_reasons=list(snapshot.degraded_reasons or []),
            stale_reasons=list(snapshot.stale_reasons or []),
            warnings=list(snapshot.warnings or []),
            last_checked_at=snapshot.last_checked_at,
            stale_after=snapshot.stale_after,
        )

    @staticmethod
    def _from_runtime_state(
        node_id: UUID,
        runtime_state: NodeRuntimeState,
        *,
        now: datetime,
        stale_after: datetime,
        refresh_scope: str,
        refresh_status: str,
        last_error: str | None = None,
        monitoring_targets: list[str] | None = None,
        metrics: dict[str, object] | None = None,
        observability: dict[str, object] | None = None,
    ) -> NodeRuntimeSnapshot:
        return NodeRuntimeSnapshot(
            node_id=node_id,
            provider_state=runtime_state.provider_state,
            provider_reachable=runtime_state.provider_reachable,
            provider_guest_exists=runtime_state.provider_guest_exists,
            ssh_state=runtime_state.ssh_state,
            monitoring_state=runtime_state.monitoring_state,
            readiness_state=runtime_state.readiness_state,
            orchestration_state=runtime_state.orchestration_state,
            lifecycle_state=runtime_state.lifecycle_state,
            eligibility=runtime_state.eligibility.model_dump(),
            degraded_reasons=runtime_state.degraded_reasons,
            stale_reasons=runtime_state.stale_reasons,
            warnings=runtime_state.warnings,
            metrics=metrics or {},
            monitoring_targets=monitoring_targets or [],
            observability=observability or {},
            last_checked_at=runtime_state.last_checked_at or now,
            stale_after=runtime_state.stale_after or stale_after,
            refresh_scope=refresh_scope,
            refresh_status=refresh_status,
            last_error=last_error,
        )
