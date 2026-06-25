from datetime import datetime
from ipaddress import ip_address, ip_interface
from uuid import UUID

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.modules.jobs.models import JobStatus
from backend.app.modules.inventory.models import ServerEnvironment
from backend.app.modules.provisioning.models import ProvisioningBatchStatus, ProvisioningStatus


class ProxmoxTemplateRead(BaseModel):
    template_id: int
    name: str
    node: str
    type: str = "qemu"
    template_ref: str | None = None
    storage: str | None = None


class ProvisioningDiskCreate(BaseModel):
    size_gb: int = Field(ge=1)
    storage: str = Field(default="local-lvm", min_length=1, max_length=100)
    bus: str = Field(default="scsi", pattern="^(scsi|virtio|sata)$")

    @field_validator("storage", "bus")
    @classmethod
    def strip_disk_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped


class ProvisioningBootstrapItem(BaseModel):
    kind: Literal["profile", "package", "deployment"]
    reference_id: str = Field(min_length=1, max_length=255)

    @field_validator("reference_id")
    @classmethod
    def strip_reference_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped


class ProvisioningCreate(BaseModel):
    vm_name: str = Field(min_length=1, max_length=255)
    provisioning_type: Literal["qemu", "lxc"] = "qemu"
    target_node: str = Field(min_length=1, max_length=100)
    template_id: int = Field(gt=0)
    template_ref: str | None = Field(default=None, max_length=500)
    new_vm_id: int = Field(gt=0)
    cpu_cores: int = Field(default=2, ge=1, le=64)
    memory_mb: int = Field(default=2048, ge=512)
    disk_gb: int = Field(default=32, ge=1)
    additional_disks: list[ProvisioningDiskCreate] = Field(default_factory=list, max_length=8)
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
    bootstrap_items: list[ProvisioningBootstrapItem] = Field(default_factory=list)

    @field_validator(
        "vm_name",
        "target_node",
        "template_ref",
        "network_bridge",
        "cloud_init_hostname",
        "cloud_init_username",
    )
    @classmethod
    def strip_required_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
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

    @model_validator(mode="after")
    def validate_lxc_template_ref(self) -> Self:
        if self.provisioning_type == "lxc" and not self.template_ref:
            raise ValueError("template_ref is required for LXC provisioning")
        return self

    @model_validator(mode="after")
    def populate_bootstrap_items(self) -> Self:
        if not self.bootstrap_items:
            self.bootstrap_items = [
                *[
                    ProvisioningBootstrapItem(kind="profile", reference_id=profile_id)
                    for profile_id in self.bootstrap_profile_ids
                ],
                *[
                    ProvisioningBootstrapItem(kind="package", reference_id=package_id)
                    for package_id in self.bootstrap_package_ids
                ],
            ]
        self.bootstrap_profile_ids = [
            item.reference_id for item in self.bootstrap_items if item.kind == "profile"
        ]
        self.bootstrap_package_ids = [
            item.reference_id for item in self.bootstrap_items if item.kind == "package"
        ]
        return self


class ProvisioningBlueprintBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    target_node: str = Field(min_length=1, max_length=100)
    template_id: int = Field(gt=0)
    cpu_cores: int = Field(default=2, ge=1, le=64)
    memory_mb: int = Field(default=2048, ge=512)
    disk_gb: int = Field(default=32, ge=1)
    additional_disks: list[ProvisioningDiskCreate] = Field(default_factory=list, max_length=8)
    network_bridge: str = Field(default="vmbr0", min_length=1, max_length=100)
    environment: ServerEnvironment = ServerEnvironment.LAB
    tags: list[str] = Field(default_factory=list)
    start_on_boot: bool = False
    cloud_init_username: str = Field(default="ubuntu", min_length=1, max_length=100)
    ssh_public_key: str | None = None
    gateway: str
    dns_servers: list[str] = Field(default_factory=list)
    bootstrap_profile_ids: list[str] = Field(default_factory=list)
    bootstrap_package_ids: list[str] = Field(default_factory=list)
    bootstrap_items: list[ProvisioningBootstrapItem] = Field(default_factory=list)

    @field_validator("name", "target_node", "network_bridge", "cloud_init_username")
    @classmethod
    def strip_blueprint_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @field_validator("gateway")
    @classmethod
    def validate_blueprint_gateway(cls, value: str) -> str:
        return str(ip_address(value.strip()))

    @field_validator("tags", "dns_servers", "bootstrap_profile_ids", "bootstrap_package_ids")
    @classmethod
    def normalize_blueprint_list(cls, value: list[str]) -> list[str]:
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
    def validate_blueprint_dns_servers(cls, value: list[str]) -> list[str]:
        return [str(ip_address(item)) for item in value]

    @model_validator(mode="after")
    def populate_blueprint_bootstrap_items(self) -> Self:
        if not self.bootstrap_items:
            self.bootstrap_items = [
                *[
                    ProvisioningBootstrapItem(kind="profile", reference_id=profile_id)
                    for profile_id in self.bootstrap_profile_ids
                ],
                *[
                    ProvisioningBootstrapItem(kind="package", reference_id=package_id)
                    for package_id in self.bootstrap_package_ids
                ],
            ]
        self.bootstrap_profile_ids = [
            item.reference_id for item in self.bootstrap_items if item.kind == "profile"
        ]
        self.bootstrap_package_ids = [
            item.reference_id for item in self.bootstrap_items if item.kind == "package"
        ]
        return self


class ProvisioningBlueprintCreate(ProvisioningBlueprintBase):
    pass


class ProvisioningBlueprintUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    target_node: str | None = Field(default=None, min_length=1, max_length=100)
    template_id: int | None = Field(default=None, gt=0)
    cpu_cores: int | None = Field(default=None, ge=1, le=64)
    memory_mb: int | None = Field(default=None, ge=512)
    disk_gb: int | None = Field(default=None, ge=1)
    additional_disks: list[ProvisioningDiskCreate] | None = Field(default=None, max_length=8)
    network_bridge: str | None = Field(default=None, min_length=1, max_length=100)
    environment: ServerEnvironment | None = None
    tags: list[str] | None = None
    start_on_boot: bool | None = None
    cloud_init_username: str | None = Field(default=None, min_length=1, max_length=100)
    ssh_public_key: str | None = None
    gateway: str | None = None
    dns_servers: list[str] | None = None
    bootstrap_profile_ids: list[str] | None = None
    bootstrap_package_ids: list[str] | None = None
    bootstrap_items: list[ProvisioningBootstrapItem] | None = None

    @field_validator("name", "target_node", "network_bridge", "cloud_init_username")
    @classmethod
    def strip_optional_blueprint_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @field_validator("gateway")
    @classmethod
    def validate_optional_gateway(cls, value: str | None) -> str | None:
        return str(ip_address(value.strip())) if value is not None else None

    @field_validator("tags", "dns_servers", "bootstrap_profile_ids", "bootstrap_package_ids")
    @classmethod
    def normalize_optional_list(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
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
    def validate_optional_dns_servers(cls, value: list[str] | None) -> list[str] | None:
        return [str(ip_address(item)) for item in value] if value is not None else None

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> Self:
        if not self.model_dump(exclude_unset=True):
            raise ValueError("At least one field must be provided")
        return self


class ProvisioningBlueprintRead(ProvisioningBlueprintBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProvisioningBootstrapTemplateBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    bootstrap_items: list[ProvisioningBootstrapItem] = Field(default_factory=list, min_length=1)

    @field_validator("name")
    @classmethod
    def strip_template_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped


class ProvisioningBootstrapTemplateCreate(ProvisioningBootstrapTemplateBase):
    pass


class ProvisioningBootstrapTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    bootstrap_items: list[ProvisioningBootstrapItem] | None = Field(default=None, min_length=1)

    @field_validator("name")
    @classmethod
    def strip_optional_template_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @model_validator(mode="after")
    def require_template_update_field(self) -> Self:
        if not self.model_dump(exclude_unset=True):
            raise ValueError("At least one field must be provided")
        return self


class ProvisioningBootstrapTemplateRead(ProvisioningBootstrapTemplateBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProvisioningBootstrapJobRead(BaseModel):
    id: UUID
    operation_type: str
    command: str
    status: JobStatus
    stdout: str | None = None
    stderr: str | None = None
    exit_code: int | None = None
    target_hostname: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ProvisioningRead(BaseModel):
    id: UUID
    vm_name: str
    provisioning_type: str = "qemu"
    target_node: str
    template_id: int
    template_ref: str | None = None
    new_vm_id: int
    cpu_cores: int
    memory_mb: int
    disk_gb: int
    additional_disks: list[dict] = Field(default_factory=list)
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
    bootstrap_items: list[ProvisioningBootstrapItem] = Field(default_factory=list)
    bootstrap_job_ids: list[str]
    bootstrap_jobs: list[ProvisioningBootstrapJobRead] = Field(default_factory=list)
    batch_id: UUID | None = None
    batch_index: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProvisioningBatchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    blueprint_id: UUID
    count: int = Field(ge=1, le=25)
    vm_name_pattern: str = Field(min_length=1, max_length=255)
    hostname_pattern: str | None = Field(default=None, min_length=1, max_length=255)
    starting_vm_id: int = Field(gt=0)
    starting_ip_cidr: str
    cloud_init_password: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name", "vm_name_pattern", "hostname_pattern")
    @classmethod
    def strip_batch_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @field_validator("starting_ip_cidr")
    @classmethod
    def validate_batch_starting_ip(cls, value: str) -> str:
        return str(ip_interface(value.strip()))

    @model_validator(mode="after")
    def validate_patterns(self) -> Self:
        if "{index}" not in self.vm_name_pattern and "{number}" not in self.vm_name_pattern:
            raise ValueError("VM name pattern must include {index} or {number}")
        if self.hostname_pattern and "{index}" not in self.hostname_pattern and "{number}" not in self.hostname_pattern:
            raise ValueError("Hostname pattern must include {index} or {number}")
        return self


class ProvisioningBatchRead(BaseModel):
    id: UUID
    name: str
    blueprint_id: UUID
    count: int
    vm_name_pattern: str
    hostname_pattern: str
    starting_vm_id: int
    starting_ip_cidr: str
    status: ProvisioningBatchStatus
    completed_count: int
    failed_count: int
    error_message: str | None = None
    requests: list[ProvisioningRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
