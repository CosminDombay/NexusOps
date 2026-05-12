from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class StandardizationProfile(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "standardization_profiles"

    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(500))
    users: Mapped[list[dict]] = mapped_column(JSON, default=list)
    groups: Mapped[list[dict]] = mapped_column(JSON, default=list)

