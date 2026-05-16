from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class StandardizationProfile(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "standardization_profiles"

    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(500))
    users: Mapped[list[dict]] = mapped_column(JSON, default=list)
    groups: Mapped[list[dict]] = mapped_column(JSON, default=list)


class InfrastructureProfileRecord(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "infrastructure_profiles"
    __table_args__ = (UniqueConstraint("slug", name="uq_infrastructure_profiles_slug"),)

    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    steps: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    variables: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_modified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    base_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_template_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
