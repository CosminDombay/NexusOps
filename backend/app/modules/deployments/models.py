from enum import StrEnum
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class DeploymentStatus(StrEnum):
    DRAFT = "draft"
    QUEUED = "queued"
    DEPLOYING = "deploying"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    DEGRADED = "degraded"
    STOPPED = "stopped"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Deployment(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deployments"

    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    compose_content: Mapped[str] = mapped_column(Text)
    env_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    credential_refs: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[DeploymentStatus] = mapped_column(
        Enum(
            DeploymentStatus,
            name="deployment_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=DeploymentStatus.DRAFT,
        nullable=False,
        index=True,
    )


class DeploymentTarget(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deployment_targets"

    deployment_id: Mapped[UUID] = mapped_column(ForeignKey("deployments.id"), index=True)
    server_id: Mapped[UUID] = mapped_column(ForeignKey("servers.id"), index=True)
    remote_path: Mapped[str] = mapped_column(String(500), default="/opt/nexusops/deployments")
    status: Mapped[DeploymentStatus] = mapped_column(
        Enum(
            DeploymentStatus,
            name="deployment_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=DeploymentStatus.DRAFT,
        nullable=False,
        index=True,
    )
    last_job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    runtime_state: Mapped[str] = mapped_column(String(50), default="unknown", nullable=False, index=True)
    health_state: Mapped[str] = mapped_column(String(50), default="unknown", nullable=False, index=True)
    sync_status: Mapped[str] = mapped_column(String(50), default="unknown", nullable=False, index=True)
    runtime_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    runtime_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    runtime_containers: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list, nullable=False)
    missing_services: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class DeploymentRevision(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deployment_revisions"

    deployment_id: Mapped[UUID] = mapped_column(ForeignKey("deployments.id"), index=True)
    server_id: Mapped[UUID] = mapped_column(ForeignKey("servers.id"), index=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    operation: Mapped[str] = mapped_column(String(50), index=True)
    compose_content: Mapped[str] = mapped_column(Text)
    env_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    status: Mapped[DeploymentStatus] = mapped_column(
        Enum(
            DeploymentStatus,
            name="deployment_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=DeploymentStatus.DEPLOYING,
        nullable=False,
        index=True,
    )
    stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr: Mapped[str | None] = mapped_column(Text, nullable=True)


class DeploymentExecution(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deployment_executions"

    deployment_id: Mapped[UUID] = mapped_column(ForeignKey("deployments.id"), index=True)
    operation: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[DeploymentStatus] = mapped_column(
        Enum(
            DeploymentStatus,
            name="deployment_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=DeploymentStatus.QUEUED,
        nullable=False,
        index=True,
    )
    trigger_source: Mapped[str] = mapped_column(String(100), default="manual", nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # TODO: promote target success/failure counters and execution owner fields to typed columns.
    result_summary: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class DeploymentTargetExecution(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deployment_target_executions"

    execution_id: Mapped[UUID] = mapped_column(ForeignKey("deployment_executions.id"), index=True)
    deployment_id: Mapped[UUID] = mapped_column(ForeignKey("deployments.id"), index=True)
    target_id: Mapped[UUID] = mapped_column(ForeignKey("deployment_targets.id"), index=True)
    server_id: Mapped[UUID] = mapped_column(ForeignKey("servers.id"), index=True)
    status: Mapped[DeploymentStatus] = mapped_column(
        Enum(
            DeploymentStatus,
            name="deployment_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=DeploymentStatus.QUEUED,
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    revision_id: Mapped[UUID | None] = mapped_column(ForeignKey("deployment_revisions.id"), nullable=True)
    stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
