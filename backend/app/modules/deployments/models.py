from enum import StrEnum
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class DeploymentStatus(StrEnum):
    DRAFT = "draft"
    DEPLOYING = "deploying"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


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
