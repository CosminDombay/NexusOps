from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class IntegrationType(StrEnum):
    INFRASTRUCTURE_PROVIDER = "infrastructure_provider"
    MONITORING = "monitoring"
    NETWORKING = "networking"
    DATABASE = "database"


class IntegrationProviderType(StrEnum):
    PROXMOX = "proxmox"
    PROMETHEUS = "prometheus"
    GRAFANA = "grafana"
    LOKI = "loki"
    TAILSCALE = "tailscale"
    CUSTOM = "custom"


class IntegrationState(StrEnum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    DISABLED = "disabled"
    SYNCING = "syncing"


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
    provider_type: Mapped[IntegrationProviderType] = mapped_column(
        Enum(
            IntegrationProviderType,
            name="integration_provider_type",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=IntegrationProviderType.CUSTOM,
        nullable=False,
        index=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    state: Mapped[IntegrationState] = mapped_column(
        Enum(
            IntegrationState,
            name="integration_state",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=IntegrationState.DISCONNECTED,
        nullable=False,
        index=True,
    )
    config: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    credential_refs: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    last_successful_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deleted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delete_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
