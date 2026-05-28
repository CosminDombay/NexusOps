from pydantic import BaseModel, Field

from backend.app.modules.runtime_state.schemas import NodeRuntimeState


class ProxmoxNodeRead(BaseModel):
    integration_id: str | None = None
    integration_name: str | None = None
    name: str
    status: str = "unknown"
    management_ip: str | None = None
    cpu_usage: float | None = None
    memory_used: int | None = None
    memory_total: int | None = None
    storage_used: int | None = None
    storage_total: int | None = None
    uptime_seconds: int | None = None
    vm_count: int = 0
    running_vm_count: int = 0
    lxc_count: int = 0
    running_lxc_count: int = 0
    inventory_server_id: str | None = None
    inventory_hostname: str | None = None
    inventory_lifecycle_state: str | None = None
    inventory_sync_status: str = "unmanaged"
    capabilities: list[str] = Field(default_factory=list)
    runtime_state: NodeRuntimeState | None = None


class ProxmoxVmRead(BaseModel):
    integration_id: str | None = None
    integration_name: str | None = None
    vm_id: int
    name: str
    node: str
    type: str
    status: str = "unknown"
    cpu_usage: float | None = None
    memory_used: int | None = None
    memory_total: int | None = None
    disk_used: int | None = None
    disk_total: int | None = None
    uptime_seconds: int | None = None
    ip_address: str | None = None
    ip_addresses: list[str] = Field(default_factory=list)
    template: bool = False
    template_ref: str | None = None
    source_template: str | None = None
    operational_readiness: str = "discovered"
    readiness_notes: list[str] = Field(default_factory=list)
    inventory_server_id: str | None = None
    inventory_hostname: str | None = None
    inventory_lifecycle_state: str | None = None
    inventory_sync_status: str = "unmanaged"
    inventory_notes: list[str] = Field(default_factory=list)
    runtime_state: NodeRuntimeState | None = None


class ProxmoxStorageRead(BaseModel):
    storage: str
    node: str | None = None
    type: str | None = None
    content: list[str] = Field(default_factory=list)
    active: bool | None = None
    enabled: bool | None = None
    shared: bool | None = None
    used_bytes: int | None = None
    total_bytes: int | None = None
    available_bytes: int | None = None


class ProxmoxVmActionRead(BaseModel):
    vm_id: int
    name: str
    node: str
    type: str
    action: str
    status: str
    task_id: str | None = None
    message: str


class ProxmoxGuestSyncRead(BaseModel):
    discovered_count: int
    imported_count: int
    updated_count: int
    skipped_count: int
    guests: list[ProxmoxVmRead]
    skipped: list[str] = Field(default_factory=list)


class ProxmoxInventorySanitizeRead(BaseModel):
    deleted_count: int
    skipped_count: int
    deleted: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)


class ProxmoxClusterSummaryRead(BaseModel):
    node_count: int
    online_node_count: int
    vm_count: int
    running_vm_count: int
    stopped_vm_count: int
    cpu_usage: float | None = None
    memory_used: int | None = None
    memory_total: int | None = None


class ProxmoxDashboardRead(BaseModel):
    summary: ProxmoxClusterSummaryRead
    nodes: list[ProxmoxNodeRead]
    vms: list[ProxmoxVmRead]


class ProxmoxNodeDetailRead(BaseModel):
    node: ProxmoxNodeRead
    vms: list[ProxmoxVmRead]
    storage_usage: list[dict[str, object]] = Field(default_factory=list)
    network_interfaces: list[dict[str, object]] = Field(default_factory=list)
    detected_services: list[str] = Field(default_factory=list)
    placeholders: list[str] = Field(default_factory=lambda: ["wake_on_lan", "host_reboot", "maintenance_mode"])


class ProxmoxHostSyncRead(BaseModel):
    discovered_count: int
    imported_count: int
    updated_count: int
    skipped_count: int
    hosts: list[ProxmoxNodeRead]
    skipped: list[str] = Field(default_factory=list)
