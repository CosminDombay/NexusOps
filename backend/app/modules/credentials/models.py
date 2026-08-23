from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class Credential(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "credentials"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    credential_type: Mapped[str] = mapped_column(
        Enum(
            "password",
            "ssh_password",
            "ssh_key",
            "api_token",
            "env_secret",
            name="credential_type",
        ),
        nullable=False,
        index=True,
    )
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    encrypted_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    private_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    passphrase: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    scope: Mapped[str] = mapped_column(
        Enum("global", "project", "environment", name="credential_scope"),
        default="global",
        nullable=False,
        index=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deleted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delete_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class CredentialUsage(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "credential_usages"

    credential_id: Mapped[UUID] = mapped_column(
        ForeignKey("credentials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    used_by_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    used_by_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    purpose: Mapped[str | None] = mapped_column(String(255), nullable=True)
