from datetime import datetime

from uuid import UUID

from sqlalchemy import Boolean, DateTime, JSON, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from backend.app.common.constants import (
    ServerStatus,
    ServerEnvironment,
    ServerSshAuthMethod,
    ManagedNodeType,
    ManagementState,
    InventoryLifecycleState,
    InventorySyncStatus,
    InventoryHealthStatus,
)


class Server(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "servers"
    __table_args__ = (
        UniqueConstraint("hostname", name="uq_servers_hostname"),
        UniqueConstraint("ip_address", name="uq_servers_ip_address"),
    )

    hostname: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    ip_address: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    operating_system: Mapped[str] = mapped_column(String(150), nullable=False)
    vmid: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    node_type: Mapped[ManagedNodeType] = mapped_column(
        Enum(
            ManagedNodeType,
            name="managed_node_type",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=ManagedNodeType.PHYSICAL,
        nullable=False,
        index=True,
    )
    environment: Mapped[ServerEnvironment] = mapped_column(
        Enum(ServerEnvironment, name="server_environment"),
        nullable=False,
        index=True,
    )
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    ssh_port: Mapped[int] = mapped_column(Integer, default=22, nullable=False)
    ssh_username: Mapped[str] = mapped_column(String(100), nullable=False)
    ssh_auth_method: Mapped[ServerSshAuthMethod] = mapped_column(
        Enum(
            ServerSshAuthMethod,
            name="server_ssh_auth_method",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=ServerSshAuthMethod.KEY,
        nullable=False,
    )
    ssh_password: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ssh_private_key_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    trusted_ssh_host_key_sha256: Mapped[str | None] = mapped_column(String(95), nullable=True)
    trusted_ssh_host_key_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    credential_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("credentials.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[ServerStatus] = mapped_column(
        Enum(ServerStatus),
        default=ServerStatus.UNKNOWN,
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(100), default="manual", nullable=False, index=True)
    integration_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("integrations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(100), default="manual", nullable=False, index=True)
    managed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    management_state: Mapped[ManagementState] = mapped_column(
        Enum(
            ManagementState,
            name="management_state",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=ManagementState.MANAGED,
        nullable=False,
        index=True,
    )
    lifecycle_state: Mapped[InventoryLifecycleState] = mapped_column(
        Enum(
            InventoryLifecycleState,
            name="inventory_lifecycle_state",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=InventoryLifecycleState.MANAGED,
        nullable=False,
        index=True,
    )
    sync_status: Mapped[InventorySyncStatus] = mapped_column(
        Enum(
            InventorySyncStatus,
            name="inventory_sync_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=InventorySyncStatus.UNKNOWN,
        nullable=False,
        index=True,
    )
    sync_state: Mapped[InventorySyncStatus] = mapped_column(
        Enum(
            InventorySyncStatus,
            name="inventory_sync_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=InventorySyncStatus.UNKNOWN,
        nullable=False,
        index=True,
    )
    provider_node: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    monitoring_interface: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    monitoring_target: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    monitoring_strategy: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    provider_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    sync_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stale_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_health_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_health_status: Mapped[InventoryHealthStatus] = mapped_column(
        Enum(
            InventoryHealthStatus,
            name="inventory_health_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=InventoryHealthStatus.UNKNOWN,
        nullable=False,
        index=True,
    )
    last_health_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
