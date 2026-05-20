export type ProxmoxNode = {
  name: string;
  status: string;
  management_ip: string | null;
  cpu_usage: number | null;
  memory_used: number | null;
  memory_total: number | null;
  storage_used: number | null;
  storage_total: number | null;
  uptime_seconds: number | null;
  vm_count: number;
  running_vm_count: number;
  lxc_count: number;
  running_lxc_count: number;
  inventory_server_id: string | null;
  inventory_hostname: string | null;
  inventory_lifecycle_state: string | null;
  inventory_sync_status: 'unknown' | 'synced' | 'unmanaged' | 'orphaned' | 'mismatch' | 'archived';
  capabilities: string[];
};

export type ProxmoxVm = {
  vm_id: number;
  name: string;
  node: string;
  type: string;
  status: string;
  cpu_usage: number | null;
  memory_used: number | null;
  memory_total: number | null;
  disk_used: number | null;
  disk_total: number | null;
  uptime_seconds: number | null;
  ip_address: string | null;
  ip_addresses: string[];
  template: boolean;
  template_ref: string | null;
  source_template: string | null;
  operational_readiness: string;
  readiness_notes: string[];
  inventory_server_id: string | null;
  inventory_hostname: string | null;
  inventory_lifecycle_state: string | null;
  inventory_sync_status: 'unknown' | 'synced' | 'unmanaged' | 'orphaned' | 'mismatch' | 'archived';
  inventory_notes: string[];
};

export type ProxmoxClusterSummary = {
  node_count: number;
  online_node_count: number;
  vm_count: number;
  running_vm_count: number;
  stopped_vm_count: number;
  cpu_usage: number | null;
  memory_used: number | null;
  memory_total: number | null;
};

export type ProxmoxDashboard = {
  summary: ProxmoxClusterSummary;
  nodes: ProxmoxNode[];
  vms: ProxmoxVm[];
};

export type ProxmoxNodeDetail = {
  node: ProxmoxNode;
  vms: ProxmoxVm[];
  storage_usage: Array<Record<string, unknown>>;
  network_interfaces: Array<Record<string, unknown>>;
  detected_services: string[];
  placeholders: string[];
};

export type ProxmoxHostSyncResult = {
  discovered_count: number;
  imported_count: number;
  updated_count: number;
  skipped_count: number;
  hosts: ProxmoxNode[];
  skipped: string[];
};

export type ProxmoxGuestSyncResult = {
  discovered_count: number;
  imported_count: number;
  updated_count: number;
  skipped_count: number;
  guests: ProxmoxVm[];
  skipped: string[];
};

export type ProxmoxVmAction = 'start' | 'stop' | 'reboot' | 'shutdown' | 'delete';

export type ProxmoxVmActionResponse = {
  vm_id: number;
  name: string;
  node: string;
  type: string;
  action: ProxmoxVmAction;
  status: string;
  task_id: string | null;
  message: string;
};
