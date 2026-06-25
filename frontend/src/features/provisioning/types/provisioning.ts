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
  template_ref: string | null;
  storage: string | null;
};

export type ProxmoxStorage = {
  storage: string;
  node: string | null;
  type: string | null;
  content: string[];
  active: boolean | null;
  enabled: boolean | null;
  shared: boolean | null;
  used_bytes: number | null;
  total_bytes: number | null;
  available_bytes: number | null;
};

export type ProvisioningRequest = {
  id: string;
  vm_name: string;
  provisioning_type: string;
  target_node: string;
  template_id: number;
  template_ref: string | null;
  new_vm_id: number;
  cpu_cores: number;
  memory_mb: number;
  disk_gb: number;
  additional_disks: ProvisioningDisk[];
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
  bootstrap_items: ProvisioningBootstrapItem[];
  bootstrap_profile_ids: string[];
  bootstrap_package_ids: string[];
  bootstrap_job_ids: string[];
  bootstrap_jobs: ProvisioningBootstrapJob[];
  batch_id: string | null;
  batch_index: number | null;
  created_at: string;
  updated_at: string;
};

export type ProvisioningBootstrapJob = {
  id: string;
  operation_type: string;
  command: string;
  status: string;
  stdout: string | null;
  stderr: string | null;
  exit_code: number | null;
  target_hostname: string | null;
  created_at: string;
  completed_at: string | null;
};

export type ProvisioningDisk = {
  size_gb: number;
  storage: string;
  bus: 'scsi' | 'virtio' | 'sata';
};

export type ProvisioningBootstrapItem = {
  kind: 'profile' | 'package' | 'deployment';
  reference_id: string;
};

export type CreateProvisioningPayload = {
  vm_name: string;
  provisioning_type: 'qemu' | 'lxc';
  target_node: string;
  template_id: number;
  template_ref: string | null;
  new_vm_id: number;
  cpu_cores: number;
  memory_mb: number;
  disk_gb: number;
  additional_disks: ProvisioningDisk[];
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
  bootstrap_items: ProvisioningBootstrapItem[];
  bootstrap_profile_ids: string[];
  bootstrap_package_ids: string[];
};

export type ProvisioningBlueprint = {
  id: string;
  name: string;
  description: string | null;
  target_node: string;
  template_id: number;
  cpu_cores: number;
  memory_mb: number;
  disk_gb: number;
  additional_disks: ProvisioningDisk[];
  network_bridge: string;
  environment: string;
  tags: string[];
  start_on_boot: boolean;
  cloud_init_username: string;
  ssh_public_key: string | null;
  gateway: string;
  dns_servers: string[];
  bootstrap_items: ProvisioningBootstrapItem[];
  bootstrap_profile_ids: string[];
  bootstrap_package_ids: string[];
  created_at: string;
  updated_at: string;
};

export type ProvisioningBootstrapTemplate = {
  id: string;
  name: string;
  description: string | null;
  bootstrap_items: ProvisioningBootstrapItem[];
  created_at: string;
  updated_at: string;
};

export type CreateProvisioningBootstrapTemplatePayload = Omit<
  ProvisioningBootstrapTemplate,
  'id' | 'created_at' | 'updated_at'
>;

export type UpdateProvisioningBootstrapTemplatePayload = Partial<CreateProvisioningBootstrapTemplatePayload>;

export type CreateProvisioningBlueprintPayload = Omit<ProvisioningBlueprint, 'id' | 'created_at' | 'updated_at'>;

export type UpdateProvisioningBlueprintPayload = Partial<CreateProvisioningBlueprintPayload>;

export type ProvisioningBatchStatus =
  | 'requested'
  | 'running'
  | 'completed'
  | 'partial_failed'
  | 'failed';

export type ProvisioningBatch = {
  id: string;
  name: string;
  blueprint_id: string;
  count: number;
  vm_name_pattern: string;
  hostname_pattern: string;
  starting_vm_id: number;
  starting_ip_cidr: string;
  status: ProvisioningBatchStatus;
  completed_count: number;
  failed_count: number;
  error_message: string | null;
  requests: ProvisioningRequest[];
  created_at: string;
  updated_at: string;
};

export type CreateProvisioningBatchPayload = {
  name: string;
  blueprint_id: string;
  count: number;
  vm_name_pattern: string;
  hostname_pattern: string | null;
  starting_vm_id: number;
  starting_ip_cidr: string;
  cloud_init_password: string | null;
  description: string | null;
};
