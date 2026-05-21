from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select

from backend.app.common.repository import BaseRepository
from backend.app.modules.runtime_state.models import (
    NodeRuntimeSnapshot,
    RuntimeRefreshEvent,
    RuntimeRefreshStatus,
)


class NodeRuntimeSnapshotRepository(BaseRepository[NodeRuntimeSnapshot]):
    async def get_by_node_id(self, node_id: UUID) -> NodeRuntimeSnapshot | None:
        result = await self.session.execute(
            select(NodeRuntimeSnapshot).where(NodeRuntimeSnapshot.node_id == node_id)
        )
        return result.scalar_one_or_none()

    async def list_by_node_ids(self, node_ids: Iterable[UUID]) -> dict[UUID, NodeRuntimeSnapshot]:
        ids = list(node_ids)
        if not ids:
            return {}
        result = await self.session.execute(
            select(NodeRuntimeSnapshot).where(NodeRuntimeSnapshot.node_id.in_(ids))
        )
        return {snapshot.node_id: snapshot for snapshot in result.scalars().all()}

    async def upsert(self, snapshot: NodeRuntimeSnapshot) -> NodeRuntimeSnapshot:
        existing = await self.get_by_node_id(snapshot.node_id)
        if existing is None:
            self.session.add(snapshot)
            await self.session.flush()
            await self.session.refresh(snapshot)
            return snapshot

        for key in (
            "provider_state",
            "provider_reachable",
            "provider_guest_exists",
            "ssh_state",
            "monitoring_state",
            "readiness_state",
            "orchestration_state",
            "lifecycle_state",
            "eligibility",
            "degraded_reasons",
            "stale_reasons",
            "warnings",
            "metrics",
            "monitoring_targets",
            "observability",
            "last_checked_at",
            "stale_after",
            "refresh_scope",
            "refresh_status",
            "last_error",
        ):
            setattr(existing, key, getattr(snapshot, key))
        await self.session.flush()
        return existing


class RuntimeRefreshEventRepository(BaseRepository[RuntimeRefreshEvent]):
    async def create(self, event: RuntimeRefreshEvent) -> RuntimeRefreshEvent:
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event


class RuntimeRefreshStatusRepository(BaseRepository[RuntimeRefreshStatus]):
    async def get_by_scope(self, scope: str) -> RuntimeRefreshStatus | None:
        result = await self.session.execute(
            select(RuntimeRefreshStatus).where(RuntimeRefreshStatus.scope == scope)
        )
        return result.scalar_one_or_none()

    async def upsert(self, status: RuntimeRefreshStatus) -> RuntimeRefreshStatus:
        existing = await self.get_by_scope(status.scope)
        if existing is None:
            self.session.add(status)
            await self.session.flush()
            await self.session.refresh(status)
            return status
        existing.status = status.status
        existing.started_at = status.started_at
        existing.finished_at = status.finished_at
        existing.last_error = status.last_error
        existing.metadata_json = status.metadata_json
        await self.session.flush()
        return existing

    async def list(self) -> list[RuntimeRefreshStatus]:
        result = await self.session.execute(select(RuntimeRefreshStatus).order_by(RuntimeRefreshStatus.scope))
        return list(result.scalars().all())
