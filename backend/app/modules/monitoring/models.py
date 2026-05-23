from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class MonitoringState(StrEnum):
    MONITORED = "monitored"
    PARTIAL = "partial"
    UNMONITORED = "unmonitored"
    STALE = "stale"
    UNKNOWN = "unknown"


class MonitoringComponentStatus(StrEnum):
    HEALTHY = "healthy"
    UNAVAILABLE = "unavailable"
    NOT_CONFIGURED = "not_configured"
    UNKNOWN = "unknown"


class MetricSample(Base, UuidPrimaryKeyMixin):
    __tablename__ = "metric_samples"

    server_id: Mapped[UUID] = mapped_column(ForeignKey("servers.id"), index=True)
    metric_name: Mapped[str] = mapped_column(String(100), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class MonitoringSnapshot(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "monitoring_snapshots"
    __table_args__ = (UniqueConstraint("server_id", name="uq_monitoring_snapshots_server_id"),)

    server_id: Mapped[UUID] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True)
    integration_id: Mapped[UUID | None] = mapped_column(ForeignKey("integrations.id", ondelete="SET NULL"), nullable=True, index=True)
    monitoring_state: Mapped[MonitoringState] = mapped_column(
        Enum(
            MonitoringState,
            name="monitoring_state",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=MonitoringState.UNKNOWN,
        nullable=False,
        index=True,
    )
    node_exporter_status: Mapped[MonitoringComponentStatus] = mapped_column(
        Enum(
            MonitoringComponentStatus,
            name="monitoring_component_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=MonitoringComponentStatus.UNKNOWN,
        nullable=False,
    )
    promtail_status: Mapped[MonitoringComponentStatus] = mapped_column(
        Enum(
            MonitoringComponentStatus,
            name="monitoring_component_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=MonitoringComponentStatus.UNKNOWN,
        nullable=False,
    )
    cadvisor_status: Mapped[MonitoringComponentStatus] = mapped_column(
        Enum(
            MonitoringComponentStatus,
            name="monitoring_component_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=MonitoringComponentStatus.UNKNOWN,
        nullable=False,
    )
    prometheus_target_health: Mapped[MonitoringComponentStatus] = mapped_column(
        Enum(
            MonitoringComponentStatus,
            name="monitoring_component_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=MonitoringComponentStatus.UNKNOWN,
        nullable=False,
    )
    monitoring_target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    grafana_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_successful_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    stale_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)


class MonitoringValidationAttempt(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "monitoring_validation_attempts"

    server_id: Mapped[UUID] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True)
    monitoring_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("monitoring_snapshots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    audit_event_id: Mapped[UUID | None] = mapped_column(ForeignKey("audit_events.id", ondelete="SET NULL"), nullable=True, index=True)
    validation_method: Mapped[str] = mapped_column(String(100), nullable=False)
    component_results: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    monitoring_state: Mapped[MonitoringState] = mapped_column(
        Enum(
            MonitoringState,
            name="monitoring_state",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=MonitoringState.UNKNOWN,
        nullable=False,
        index=True,
    )
    result: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    failure_reason: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
