from enum import StrEnum
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String, Text
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

