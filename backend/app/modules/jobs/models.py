from enum import StrEnum
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


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
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
