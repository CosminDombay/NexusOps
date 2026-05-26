from enum import StrEnum
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class JobStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    COMPLETED = "completed"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STALE = "stale"


class Job(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_status_created_at", "status", "created_at"),
        Index("ix_jobs_target_status", "target_server_id", "status"),
    )

    target_server_id: Mapped[UUID] = mapped_column(ForeignKey("servers.id"), index=True)
    operation_type: Mapped[str] = mapped_column(String(100), index=True)
    command: Mapped[str] = mapped_column(Text)
    actual_command: Mapped[str | None] = mapped_column(Text, nullable=True)
    command_display: Mapped[str | None] = mapped_column(Text, nullable=True)
    command_policy: Mapped[str] = mapped_column(String(50), default="allowed", nullable=False, index=True)
    command_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    initiated_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    initiated_by_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[JobStatus] = mapped_column(
        Enum(
            JobStatus,
            name="job_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=JobStatus.PENDING,
        nullable=False,
        index=True,
    )
    stdout: Mapped[str | None] = mapped_column(Text)
    stderr: Mapped[str | None] = mapped_column(Text)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    runtime_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    execution_origin: Mapped[str] = mapped_column(String(100), default="manual", nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(100), index=True)
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # TODO: promote stable runtime metadata keys to typed columns before distributed execution.
    runtime_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # TODO: move high-volume output events to an append-only runtime event table before streaming support.
    output_events: Mapped[list] = mapped_column(JSON, default=list, nullable=False)


class CustomOperationalAction(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "custom_operational_actions"

    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str] = mapped_column(String(100), index=True, default="Custom")
    description: Mapped[str] = mapped_column(Text, default="")
    command: Mapped[str] = mapped_column(Text)
    destructive: Mapped[bool] = mapped_column(default=False, nullable=False)


class JobExecutionEvent(Base, UuidPrimaryKeyMixin):
    __tablename__ = "job_execution_events"
    __table_args__ = (
        Index("ix_job_execution_events_job_created", "job_id", "created_at"),
        Index("ix_job_execution_events_correlation", "correlation_id"),
    )

    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
