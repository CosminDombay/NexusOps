from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class NodeRuntimeSnapshot(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "node_runtime_snapshots"
    __table_args__ = (UniqueConstraint("node_id", name="uq_node_runtime_snapshots_node_id"),)

    node_id: Mapped[UUID] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_state: Mapped[str] = mapped_column(String(100), default="unknown", nullable=False, index=True)
    provider_reachable: Mapped[bool] = mapped_column(default=False, nullable=False)
    provider_guest_exists: Mapped[bool] = mapped_column(default=False, nullable=False)
    ssh_state: Mapped[str] = mapped_column(String(100), default="unknown", nullable=False, index=True)
    monitoring_state: Mapped[str] = mapped_column(String(100), default="unknown", nullable=False, index=True)
    readiness_state: Mapped[str] = mapped_column(String(100), default="unknown", nullable=False, index=True)
    orchestration_state: Mapped[str] = mapped_column(String(100), default="unknown", nullable=False, index=True)
    lifecycle_state: Mapped[str] = mapped_column(String(100), default="unknown", nullable=False, index=True)
    eligibility: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    degraded_reasons: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    stale_reasons: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    metrics: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    monitoring_targets: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    observability: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    stale_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    refresh_scope: Mapped[str] = mapped_column(String(100), default="inventory", nullable=False, index=True)
    refresh_status: Mapped[str] = mapped_column(String(50), default="success", nullable=False, index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class RuntimeRefreshEvent(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "runtime_refresh_events"

    scope: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    node_id: Mapped[UUID | None] = mapped_column(ForeignKey("servers.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)


class RuntimeRefreshStatus(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "runtime_refresh_status"
    __table_args__ = (UniqueConstraint("scope", name="uq_runtime_refresh_status_scope"),)

    scope: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="unknown", nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
