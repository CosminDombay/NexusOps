from uuid import UUID

from sqlalchemy import select

from backend.app.common.repository import BaseRepository
from backend.app.modules.monitoring.models import (
    MetricSample,
    MonitoringSnapshot,
    MonitoringValidationAttempt,
)


class MetricSampleRepository(BaseRepository[MetricSample]):
    pass


class MonitoringSnapshotRepository(BaseRepository[MonitoringSnapshot]):
    async def get_by_server_id(self, server_id: UUID) -> MonitoringSnapshot | None:
        result = await self.session.execute(
            select(MonitoringSnapshot).where(MonitoringSnapshot.server_id == server_id)
        )
        return result.scalar_one_or_none()

    async def list_by_server_ids(self, server_ids) -> dict[UUID, MonitoringSnapshot]:
        ids = list(server_ids)
        if not ids:
            return {}
        result = await self.session.execute(
            select(MonitoringSnapshot).where(MonitoringSnapshot.server_id.in_(ids))
        )
        return {snapshot.server_id: snapshot for snapshot in result.scalars().all()}

    async def latest_validated(self) -> MonitoringSnapshot | None:
        result = await self.session.execute(
            select(MonitoringSnapshot)
            .where(MonitoringSnapshot.last_validated_at.is_not(None))
            .order_by(MonitoringSnapshot.last_validated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def upsert(self, snapshot: MonitoringSnapshot) -> MonitoringSnapshot:
        existing = await self.get_by_server_id(snapshot.server_id)
        if existing is None:
            self.session.add(snapshot)
            await self.session.flush()
            return snapshot
        for key in (
            "integration_id",
            "monitoring_state",
            "node_exporter_status",
            "promtail_status",
            "cadvisor_status",
            "prometheus_target_health",
            "monitoring_target",
            "grafana_url",
            "last_validated_at",
            "last_successful_check_at",
            "stale_after",
            "last_error",
            "details",
        ):
            setattr(existing, key, getattr(snapshot, key))
        await self.session.flush()
        return existing


class MonitoringValidationAttemptRepository(BaseRepository[MonitoringValidationAttempt]):
    async def create(self, attempt: MonitoringValidationAttempt) -> MonitoringValidationAttempt:
        self.session.add(attempt)
        await self.session.flush()
        await self.session.refresh(attempt)
        return attempt

    async def list_for_server(self, server_id: UUID, *, limit: int = 50) -> list[MonitoringValidationAttempt]:
        result = await self.session.execute(
            select(MonitoringValidationAttempt)
            .where(MonitoringValidationAttempt.server_id == server_id)
            .order_by(MonitoringValidationAttempt.started_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
