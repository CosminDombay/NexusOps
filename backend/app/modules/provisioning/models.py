from enum import StrEnum
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class VmStatus(StrEnum):
    REQUESTED = "requested"
    CREATING = "creating"
    RUNNING = "running"
    STOPPED = "stopped"
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

