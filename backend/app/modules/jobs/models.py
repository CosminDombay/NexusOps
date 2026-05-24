from enum import StrEnum
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text
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

    target_server_id: Mapped[UUID] = mapped_column(ForeignKey("servers.id"), index=True)
    operation_type: Mapped[str] = mapped_column(String(100), index=True)
    command: Mapped[str] = mapped_column(Text)
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
