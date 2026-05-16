from enum import StrEnum

from sqlalchemy import Boolean, Enum, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class IntegrationType(StrEnum):
    INFRASTRUCTURE_PROVIDER = "infrastructure_provider"
    MONITORING = "monitoring"
    NETWORKING = "networking"
    DATABASE = "database"


class Integration(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "integrations"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    type: Mapped[IntegrationType] = mapped_column(
        Enum(
            IntegrationType,
            name="integration_type",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        index=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    config: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
