from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class Variable(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "variables"

    key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="general", nullable=False, index=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    credential_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("credentials.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
