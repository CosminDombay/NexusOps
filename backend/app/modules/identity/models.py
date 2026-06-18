from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class IdentityExecutionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class LinuxUser(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "linux_users"

    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    shell: Mapped[str] = mapped_column(String(255), default="/bin/bash", nullable=False)
    home_directory: Mapped[str] = mapped_column(String(500), nullable=False)
    password_credential_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sudo_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sudo_nopasswd: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    managed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)


class LinuxGroup(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "linux_groups"

    name: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    members: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    managed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)


class SSHKey(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ssh_keys"

    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class PermissionTemplate(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "permission_templates"

    path: Mapped[str] = mapped_column(String(1000), nullable=False)
    owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    group: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mode: Mapped[str | None] = mapped_column(String(4), nullable=True)
    recursive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class IdentityExecution(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "identity_executions"

    operation_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    target_server_id: Mapped[UUID] = mapped_column(ForeignKey("servers.id"), index=True)
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    status: Mapped[IdentityExecutionStatus] = mapped_column(
        Enum(
            IdentityExecutionStatus,
            name="identity_execution_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=IdentityExecutionStatus.PENDING,
        nullable=False,
        index=True,
    )
    stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
