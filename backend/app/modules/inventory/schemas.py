from datetime import datetime
from ipaddress import ip_address
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.common.constants import (
    InventoryLifecycleState,
    InventoryHealthStatus,
    InventorySyncStatus,
    ServerEnvironment,
    ServerSshAuthMethod,
    ServerStatus,
)


class ServerBase(BaseModel):
    hostname: str = Field(min_length=1, max_length=255)
    ip_address: str
    operating_system: str = Field(min_length=1, max_length=150)
    vmid: str | None = Field(default=None, max_length=100)
    environment: ServerEnvironment
    tags: list[str] = Field(default_factory=list)
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_username: str = Field(min_length=1, max_length=100)
    ssh_auth_method: ServerSshAuthMethod = ServerSshAuthMethod.KEY
    ssh_password: str | None = Field(default=None, max_length=500)
    ssh_private_key_path: str | None = Field(default=None, max_length=500)
    credential_id: UUID | None = None
    status: ServerStatus = ServerStatus.UNKNOWN
    provider: str = Field(min_length=1, max_length=100)
    external_id: str | None = Field(default=None, max_length=100)
    source: str = Field(default="manual", min_length=1, max_length=100)
    managed: bool = True
    lifecycle_state: InventoryLifecycleState = InventoryLifecycleState.MANAGED
    sync_status: InventorySyncStatus = InventorySyncStatus.UNKNOWN
    provider_node: str | None = Field(default=None, max_length=100)
    provider_type: str | None = Field(default=None, max_length=50)
    provider_metadata: dict[str, object] = Field(default_factory=dict)
    last_seen_at: datetime | None = None
    last_health_check_at: datetime | None = None
    last_health_status: InventoryHealthStatus = InventoryHealthStatus.UNKNOWN
    last_health_error: str | None = Field(default=None, max_length=500)

    @field_validator("ip_address")
    @classmethod
    def validate_ip_address(cls, value: str) -> str:
        return str(ip_address(value))

    @field_validator("hostname", "provider", "ssh_username", "operating_system", "source")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        normalized = []
        seen = set()
        for tag in value:
            clean = tag.strip()
            if clean and clean not in seen:
                normalized.append(clean)
                seen.add(clean)
        return normalized

    @field_validator("ssh_password", "ssh_private_key_path")
    @classmethod
    def strip_optional_secret_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def validate_ssh_auth(self) -> Self:
        if self.credential_id is not None:
            return self
        if self.ssh_auth_method == ServerSshAuthMethod.PASSWORD and not self.ssh_password:
            raise ValueError("SSH password is required when password authentication is selected")
        return self


class ServerCreate(ServerBase):
    pass


class ServerUpdate(BaseModel):
    hostname: str | None = Field(default=None, min_length=1, max_length=255)
    ip_address: str | None = None
    operating_system: str | None = Field(default=None, min_length=1, max_length=150)
    vmid: str | None = Field(default=None, max_length=100)
    environment: ServerEnvironment | None = None
    tags: list[str] | None = None
    ssh_port: int | None = Field(default=None, ge=1, le=65535)
    ssh_username: str | None = Field(default=None, min_length=1, max_length=100)
    ssh_auth_method: ServerSshAuthMethod | None = None
    ssh_password: str | None = Field(default=None, max_length=500)
    ssh_private_key_path: str | None = Field(default=None, max_length=500)
    credential_id: UUID | None = None
    status: ServerStatus | None = None
    provider: str | None = Field(default=None, min_length=1, max_length=100)
    external_id: str | None = Field(default=None, max_length=100)
    source: str | None = Field(default=None, min_length=1, max_length=100)
    managed: bool | None = None
    lifecycle_state: InventoryLifecycleState | None = None
    sync_status: InventorySyncStatus | None = None
    provider_node: str | None = Field(default=None, max_length=100)
    provider_type: str | None = Field(default=None, max_length=50)
    provider_metadata: dict[str, object] | None = None
    last_seen_at: datetime | None = None
    last_health_check_at: datetime | None = None
    last_health_status: InventoryHealthStatus | None = None
    last_health_error: str | None = Field(default=None, max_length=500)

    @field_validator("ip_address")
    @classmethod
    def validate_ip_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(ip_address(value))

    @field_validator("hostname", "provider", "ssh_username", "operating_system", "source")
    @classmethod
    def strip_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = []
        seen = set()
        for tag in value:
            clean = tag.strip()
            if clean and clean not in seen:
                normalized.append(clean)
                seen.add(clean)
        return normalized

    @field_validator("ssh_password", "ssh_private_key_path")
    @classmethod
    def strip_optional_secret_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> Self:
        if not self.model_dump(exclude_unset=True):
            raise ValueError("At least one field must be provided")
        return self


class ServerRead(ServerBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    ssh_password: str | None = Field(default=None, exclude=True)


    model_config = ConfigDict(from_attributes=True)


class InventoryHealthCheckResult(BaseModel):
    server_id: UUID
    hostname: str
    status: InventoryHealthStatus
    checked_at: datetime
    error: str | None = None


class BulkInventoryHealthCheckRequest(BaseModel):
    server_ids: list[UUID] | None = None


class InventoryHealthSummary(BaseModel):
    total: int
    online: int
    unreachable: int
    unknown: int
    provisioning: int
    archived: int
    sync_error: int
    last_checked_at: datetime | None = None


class HostFilesystemRead(BaseModel):
    filesystem: str
    type: str | None = None
    size_bytes: int | None = None
    used_bytes: int | None = None
    available_bytes: int | None = None
    mountpoint: str


class HostSystemRead(BaseModel):
    hostname: str
    operating_system: str
    kernel: str | None = None
    uptime_seconds: int | None = None
    load_average: list[float] = Field(default_factory=list)
    cpu_model: str | None = None
    cpu_cores: int | None = None
    memory_total_bytes: int | None = None
    memory_used_bytes: int | None = None
    memory_available_bytes: int | None = None
    filesystems: list[HostFilesystemRead] = Field(default_factory=list)


class HostNetworkInterfaceRead(BaseModel):
    name: str
    addresses: list[str] = Field(default_factory=list)


class ListeningPortRead(BaseModel):
    protocol: str
    address: str
    port: int
    process: str | None = None
    service: str | None = None


class HostNetworkRead(BaseModel):
    lan_ip: str
    tailscale_ip: str | None = None
    interfaces: list[HostNetworkInterfaceRead] = Field(default_factory=list)
    listening_ports: list[ListeningPortRead] = Field(default_factory=list)


class DockerContainerRead(BaseModel):
    container_id: str
    name: str
    image: str
    status: str
    ports: str | None = None
    compose_project: str | None = None


class DockerNetworkRead(BaseModel):
    name: str
    driver: str
    scope: str


class HostDockerRead(BaseModel):
    installed: bool
    version: str | None = None
    containers: list[DockerContainerRead] = Field(default_factory=list)
    networks: list[DockerNetworkRead] = Field(default_factory=list)


class ServerListFilters(BaseModel):
    environment: ServerEnvironment | None = None
    provider: str | None = None
    search: str | None = None


class ProxmoxInventoryImport(BaseModel):
    vm_id: int
    node: str = Field(min_length=1, max_length=100)
    vm_type: str = Field(default="qemu", min_length=1, max_length=50)
    hostname: str = Field(min_length=1, max_length=255)
    ip_address: str
    operating_system: str = Field(default="cloud-init Linux", min_length=1, max_length=150)
    environment: ServerEnvironment = ServerEnvironment.LAB
    tags: list[str] = Field(default_factory=list)
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_username: str = Field(min_length=1, max_length=100)
    ssh_auth_method: ServerSshAuthMethod = ServerSshAuthMethod.KEY
    ssh_password: str | None = Field(default=None, max_length=500)
    ssh_private_key_path: str | None = Field(default=None, max_length=500)
    credential_id: UUID | None = None

    @field_validator("ip_address")
    @classmethod
    def validate_ip_address(cls, value: str) -> str:
        return str(ip_address(value))

    @field_validator("hostname", "node", "vm_type", "operating_system", "ssh_username")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        normalized = []
        seen = set()
        for tag in value:
            clean = tag.strip()
            if clean and clean not in seen:
                normalized.append(clean)
                seen.add(clean)
        return normalized

    @model_validator(mode="after")
    def validate_ssh_auth(self) -> Self:
        if self.credential_id is not None:
            return self
        if self.ssh_auth_method == ServerSshAuthMethod.PASSWORD and not self.ssh_password:
            raise ValueError("SSH password is required when password authentication is selected")
        return self
