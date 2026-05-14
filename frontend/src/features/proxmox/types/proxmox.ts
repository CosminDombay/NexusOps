export type ProxmoxNode = {
  name: string;
  status: string;
  cpu_usage: number | null;
  memory_used: number | null;
  memory_total: number | null;
  uptime_seconds: number | null;
  vm_count: number;
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

export type ProxmoxVmAction = 'start' | 'stop' | 'reboot' | 'shutdown';

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
