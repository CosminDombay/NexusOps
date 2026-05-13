from datetime import datetime
from ipaddress import ip_address, ip_interface
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.modules.inventory.models import ServerEnvironment
from backend.app.modules.provisioning.models import ProvisioningStatus


class ProxmoxTemplateRead(BaseModel):
    template_id: int
    name: str
    node: str
    type: str = "qemu"


class ProvisioningCreate(BaseModel):
    vm_name: str = Field(min_length=1, max_length=255)
    target_node: str = Field(min_length=1, max_length=100)
    template_id: int = Field(gt=0)
    new_vm_id: int = Field(gt=0)
    cpu_cores: int = Field(default=2, ge=1, le=64)
    memory_mb: int = Field(default=2048, ge=512)
    disk_gb: int = Field(default=32, ge=1)
    network_bridge: str = Field(default="vmbr0", min_length=1, max_length=100)
    environment: ServerEnvironment = ServerEnvironment.LAB
    tags: list[str] = Field(default_factory=list)
    description: str | None = Field(default=None, max_length=2000)
    start_on_boot: bool = False

    cloud_init_hostname: str = Field(min_length=1, max_length=255)
    cloud_init_username: str = Field(min_length=1, max_length=100)
    cloud_init_password: str | None = Field(default=None, max_length=500)
    ssh_public_key: str | None = None
    static_ip_cidr: str
    gateway: str
    dns_servers: list[str] = Field(default_factory=list)

    bootstrap_profile_ids: list[str] = Field(default_factory=list)
    bootstrap_package_ids: list[str] = Field(default_factory=list)

    @field_validator(
        "vm_name",
        "target_node",
        "network_bridge",
        "cloud_init_hostname",
        "cloud_init_username",
    )
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @field_validator("static_ip_cidr")
    @classmethod
    def validate_static_ip_cidr(cls, value: str) -> str:
        return str(ip_interface(value.strip()))

    @field_validator("gateway")
    @classmethod
    def validate_gateway(cls, value: str) -> str:
        return str(ip_address(value.strip()))

    @field_validator("tags", "dns_servers", "bootstrap_profile_ids", "bootstrap_package_ids")
    @classmethod
    def normalize_list(cls, value: list[str]) -> list[str]:
        normalized = []
        seen = set()
        for item in value:
            clean = item.strip()
            if clean and clean not in seen:
                normalized.append(clean)
                seen.add(clean)
        return normalized

    @field_validator("dns_servers")
    @classmethod
    def validate_dns_servers(cls, value: list[str]) -> list[str]:
        return [str(ip_address(item)) for item in value]


class ProvisioningRead(BaseModel):
    id: UUID
    vm_name: str
    target_node: str
    template_id: int
    new_vm_id: int
    cpu_cores: int
    memory_mb: int
    disk_gb: int
    network_bridge: str
    environment: str
    tags: list[str]
    description: str | None = None
    start_on_boot: bool
    cloud_init_username: str
    ssh_public_key: str | None = None
    static_ip_cidr: str
    gateway: str
    dns_servers: list[str]
    status: ProvisioningStatus
    error_message: str | None = None
    proxmox_task_ids: list[str]
    server_id: UUID | None = None
    bootstrap_profile_ids: list[str]
    bootstrap_package_ids: list[str]
    bootstrap_job_ids: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
