from pydantic import BaseModel, Field


class ProxmoxNodeRead(BaseModel):
    name: str
    status: str = "unknown"
    cpu_usage: float | None = None
    memory_used: int | None = None
    memory_total: int | None = None
    uptime_seconds: int | None = None
    vm_count: int = 0


class ProxmoxVmRead(BaseModel):
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
    inventory_server_id: str | None = None
    inventory_hostname: str | None = None
    inventory_lifecycle_state: str | None = None
    inventory_sync_status: str = "unmanaged"
    inventory_notes: list[str] = Field(default_factory=list)


class ProxmoxVmActionRead(BaseModel):
    vm_id: int
    name: str
    node: str
    type: str
    action: str
    status: str
    task_id: str | None = None
    message: str


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
