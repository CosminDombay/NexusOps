export type ProvisioningStatus =
  | 'requested'
  | 'validating_ip'
  | 'cloning'
  | 'configuring'
  | 'starting'
  | 'waiting_for_ssh'
  | 'inventory_registration'
  | 'bootstrap_running'
  | 'completed'
  | 'failed';

export type ProxmoxTemplate = {
  template_id: number;
  name: string;
  node: string;
  type: string;
};

export type ProvisioningRequest = {
  id: string;
  vm_name: string;
  target_node: string;
  template_id: number;
  new_vm_id: number;
  cpu_cores: number;
  memory_mb: number;
  disk_gb: number;
  network_bridge: string;
  environment: string;
  tags: string[];
  description: string | null;
  start_on_boot: boolean;
  cloud_init_username: string;
  ssh_public_key: string | null;
  static_ip_cidr: string;
  gateway: string;
  dns_servers: string[];
  status: ProvisioningStatus;
  error_message: string | null;
  proxmox_task_ids: string[];
  server_id: string | null;
  bootstrap_profile_ids: string[];
  bootstrap_package_ids: string[];
  bootstrap_job_ids: string[];
  created_at: string;
  updated_at: string;
};

export type CreateProvisioningPayload = {
  vm_name: string;
  target_node: string;
  template_id: number;
  new_vm_id: number;
  cpu_cores: number;
  memory_mb: number;
  disk_gb: number;
  network_bridge: string;
  environment: string;
  tags: string[];
  description: string | null;
  start_on_boot: boolean;
  cloud_init_hostname: string;
  cloud_init_username: string;
  cloud_init_password: string | null;
  ssh_public_key: string | null;
  static_ip_cidr: string;
  gateway: string;
  dns_servers: string[];
  bootstrap_profile_ids: string[];
  bootstrap_package_ids: string[];
};
