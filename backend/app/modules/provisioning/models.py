from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class VmStatus(StrEnum):
    REQUESTED = "requested"
    CREATING = "creating"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


class ProvisioningStatus(StrEnum):
    REQUESTED = "requested"
    VALIDATING_IP = "validating_ip"
    CLONING = "cloning"
    CONFIGURING = "configuring"
    STARTING = "starting"
    WAITING_FOR_SSH = "waiting_for_ssh"
    INVENTORY_REGISTRATION = "inventory_registration"
    BOOTSTRAP_RUNNING = "bootstrap_running"
    COMPLETED = "completed"
    FAILED = "failed"


class ProvisioningBatchStatus(StrEnum):
    REQUESTED = "requested"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL_FAILED = "partial_failed"
    FAILED = "failed"


class VirtualMachine(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "virtual_machines"

    name: Mapped[str] = mapped_column(String(255), index=True)
    provider: Mapped[str] = mapped_column(String(100), default="proxmox")
    provider_vm_id: Mapped[str | None] = mapped_column(String(100), index=True)
    node_name: Mapped[str | None] = mapped_column(String(100))
    cpu_cores: Mapped[int] = mapped_column(Integer)
    memory_mb: Mapped[int] = mapped_column(Integer)
    disk_gb: Mapped[int] = mapped_column(Integer)
    status: Mapped[VmStatus] = mapped_column(Enum(VmStatus), default=VmStatus.REQUESTED)
    server_id: Mapped[UUID | None] = mapped_column(ForeignKey("servers.id"))


class ProvisioningRequest(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "provisioning_requests"

    vm_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    provisioning_type: Mapped[str] = mapped_column(String(20), default="qemu", nullable=False, index=True)
    target_node: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    template_id: Mapped[int] = mapped_column(Integer, nullable=False)
    template_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    new_vm_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    cpu_cores: Mapped[int] = mapped_column(Integer, nullable=False)
    memory_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    disk_gb: Mapped[int] = mapped_column(Integer, nullable=False)
    additional_disks: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    network_bridge: Mapped[str] = mapped_column(String(100), nullable=False)
    environment: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    start_on_boot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    cloud_init_username: Mapped[str] = mapped_column(String(100), nullable=False)
    cloud_init_password: Mapped[str | None] = mapped_column(String(500))
    ssh_public_key: Mapped[str | None] = mapped_column(Text)
    static_ip_cidr: Mapped[str] = mapped_column(String(64), nullable=False)
    gateway: Mapped[str] = mapped_column(String(64), nullable=False)
    dns_servers: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    status: Mapped[ProvisioningStatus] = mapped_column(
        Enum(
            ProvisioningStatus,
            name="provisioning_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=ProvisioningStatus.REQUESTED,
        nullable=False,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    proxmox_task_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    server_id: Mapped[UUID | None] = mapped_column(ForeignKey("servers.id"))
    bootstrap_profile_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    bootstrap_package_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    bootstrap_job_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    batch_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("provisioning_batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    batch_index: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ProvisioningBlueprint(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "provisioning_blueprints"
    __table_args__ = (UniqueConstraint("name", name="uq_provisioning_blueprints_name"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    target_node: Mapped[str] = mapped_column(String(100), nullable=False)
    template_id: Mapped[int] = mapped_column(Integer, nullable=False)
    cpu_cores: Mapped[int] = mapped_column(Integer, nullable=False)
    memory_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    disk_gb: Mapped[int] = mapped_column(Integer, nullable=False)
    additional_disks: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    network_bridge: Mapped[str] = mapped_column(String(100), nullable=False)
    environment: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    start_on_boot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cloud_init_username: Mapped[str] = mapped_column(String(100), nullable=False)
    ssh_public_key: Mapped[str | None] = mapped_column(Text)
    gateway: Mapped[str] = mapped_column(String(64), nullable=False)
    dns_servers: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    bootstrap_profile_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    bootstrap_package_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class ProvisioningBatch(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "provisioning_batches"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    blueprint_id: Mapped[UUID] = mapped_column(
        ForeignKey("provisioning_blueprints.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    vm_name_pattern: Mapped[str] = mapped_column(String(255), nullable=False)
    hostname_pattern: Mapped[str] = mapped_column(String(255), nullable=False)
    starting_vm_id: Mapped[int] = mapped_column(Integer, nullable=False)
    starting_ip_cidr: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[ProvisioningBatchStatus] = mapped_column(
        Enum(
            ProvisioningBatchStatus,
            name="provisioning_batch_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=ProvisioningBatchStatus.REQUESTED,
        nullable=False,
        index=True,
    )
    completed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
