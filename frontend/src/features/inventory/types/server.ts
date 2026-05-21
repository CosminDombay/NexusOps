import type { NodeRuntimeState } from '../../runtime-state/types/runtimeState';

export type ServerEnvironment = 'development' | 'staging' | 'production' | 'testing' | 'lab';

export type ServerStatus = 'unknown' | 'online' | 'offline' | 'maintenance';

export type ServerSshAuthMethod = 'key' | 'password';

export type ManagedNodeType = 'vm' | 'lxc' | 'physical' | 'hypervisor';

export type ManagementState = 'discovered' | 'unmanaged' | 'managed' | 'retired';

export type InventoryLifecycleState =
  | 'discovered'
  | 'imported'
  | 'managed'
  | 'provisioned'
  | 'unmanaged'
  | 'deleting'
  | 'deleted'
  | 'failed'
  | 'archived'
  | 'decommissioned';

export type InventorySyncStatus = 'unknown' | 'synced' | 'unmanaged' | 'orphaned' | 'mismatch' | 'archived';

export type InventoryHealthStatus = 'online' | 'unreachable' | 'unknown' | 'provisioning' | 'archived' | 'sync_error';

export type Server = {
  id: string;
  hostname: string;
  ip_address: string;
  operating_system: string;
  vmid: string | null;
  node_type: ManagedNodeType;
  environment: ServerEnvironment;
  tags: string[];
  ssh_port: number;
  ssh_username: string;
  ssh_auth_method: ServerSshAuthMethod;
  ssh_private_key_path: string | null;
  credential_id: string | null;
  status: ServerStatus;
  provider: string;
  external_id: string | null;
  source: string;
  managed: boolean;
  management_state: ManagementState;
  lifecycle_state: InventoryLifecycleState;
  sync_status: InventorySyncStatus;
  sync_state: InventorySyncStatus;
  provider_node: string | null;
  provider_type: string | null;
  monitoring_interface: string | null;
  monitoring_target: string | null;
  monitoring_strategy: string | null;
  provider_metadata: Record<string, unknown>;
  capabilities: string[];
  last_seen_at: string | null;
  last_health_check_at: string | null;
  last_health_status: InventoryHealthStatus;
  last_health_error: string | null;
  runtime_state: NodeRuntimeState | null;
  created_at: string;
  updated_at: string;
};

export type CreateServerPayload = {
  hostname: string;
  ip_address: string;
  operating_system: string;
  node_type?: ManagedNodeType;
  environment: ServerEnvironment;
  tags?: string[];
  provider: string;
  ssh_port: number;
  ssh_username: string;
  ssh_auth_method: ServerSshAuthMethod;
  ssh_password?: string | null;
  ssh_private_key_path?: string | null;
  credential_id?: string | null;
  external_id?: string | null;
  source?: string;
  managed?: boolean;
  management_state?: ManagementState;
  lifecycle_state?: InventoryLifecycleState;
  sync_status?: InventorySyncStatus;
  sync_state?: InventorySyncStatus;
  provider_node?: string | null;
  provider_type?: string | null;
  monitoring_interface?: string | null;
  monitoring_target?: string | null;
  monitoring_strategy?: string | null;
  provider_metadata?: Record<string, unknown>;
  capabilities?: string[];
};

export type UpdateServerPayload = Partial<CreateServerPayload> & {
  status?: ServerStatus;
};

export type ImportProxmoxVmPayload = CreateServerPayload & {
  vm_id: number;
  node: string;
  vm_type: string;
};

export type InventoryHealthCheckResult = {
  server_id: string;
  hostname: string;
  status: InventoryHealthStatus;
  checked_at: string;
  error: string | null;
};

export type InventoryHealthSummary = {
  total: number;
  online: number;
  unreachable: number;
  unknown: number;
  provisioning: number;
  archived: number;
  sync_error: number;
  last_checked_at: string | null;
};

export type HostFilesystem = {
  filesystem: string;
  type: string | null;
  size_bytes: number | null;
  used_bytes: number | null;
  available_bytes: number | null;
  mountpoint: string;
};

export type HostSystem = {
  hostname: string;
  operating_system: string;
  kernel: string | null;
  uptime_seconds: number | null;
  load_average: number[];
  cpu_model: string | null;
  cpu_cores: number | null;
  memory_total_bytes: number | null;
  memory_used_bytes: number | null;
  memory_available_bytes: number | null;
  filesystems: HostFilesystem[];
};

export type HostNetworkInterface = {
  name: string;
  addresses: string[];
};

export type ListeningPort = {
  protocol: string;
  address: string;
  port: number;
  process: string | null;
  service: string | null;
};

export type HostNetwork = {
  lan_ip: string;
  tailscale_ip: string | null;
  interfaces: HostNetworkInterface[];
  listening_ports: ListeningPort[];
};

export type DockerContainer = {
  container_id: string;
  name: string;
  image: string;
  status: string;
  ports: string | null;
  compose_project: string | null;
};

export type DockerNetwork = {
  name: string;
  driver: string;
  scope: string;
};

export type HostDocker = {
  installed: boolean;
  version: string | null;
  containers: DockerContainer[];
  networks: DockerNetwork[];
};
