from enum import StrEnum
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String, Text
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

    server_id: Mapped[UUID] = mapped_column(ForeignKey("servers.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    compose_content: Mapped[str] = mapped_column(Text)
    status: Mapped[DeploymentStatus] = mapped_column(
        Enum(DeploymentStatus),
        default=DeploymentStatus.DRAFT,
    )

