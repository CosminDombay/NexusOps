from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class PackageInstallStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PackageInstallation(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "package_installations"

    server_id: Mapped[UUID] = mapped_column(ForeignKey("servers.id"), index=True)
    package_name: Mapped[str] = mapped_column(String(255))
    package_manager: Mapped[str] = mapped_column(String(50))
    requested_version: Mapped[str | None] = mapped_column(String(100))
    output: Mapped[str | None] = mapped_column(Text)
    status: Mapped[PackageInstallStatus] = mapped_column(
        Enum(PackageInstallStatus),
        default=PackageInstallStatus.PENDING,
    )


class PackageDefinitionRecord(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "package_definitions"
    __table_args__ = (UniqueConstraint("slug", name="uq_package_definitions_slug"),)

    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    supported_os: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    install_command: Mapped[str] = mapped_column(Text, nullable=False)
    uninstall_command: Mapped[str] = mapped_column(Text, default="", nullable=False)
    validation_command: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_modified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    base_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_template_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deleted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delete_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
