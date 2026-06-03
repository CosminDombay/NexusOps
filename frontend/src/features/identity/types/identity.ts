import type { BulkExecutionResponse } from '../../jobs/types/job';

export type LinuxUser = {
  id: string;
  username: string;
  shell: string;
  home_directory: string;
  sudo_enabled: boolean;
  sudo_nopasswd: boolean;
  locked: boolean;
  managed: boolean;
  created_at: string;
  updated_at: string;
};

export type LinuxGroup = {
  id: string;
  name: string;
  description: string | null;
  managed: boolean;
  created_at: string;
  updated_at: string;
};

export type UserGroupMembershipHost = {
  target_server_id: string;
  target_hostname: string | null;
  groups: string[];
  error: string | null;
};

export type UserGroupMembership = {
  username: string;
  hosts: UserGroupMembershipHost[];
};

export type GroupMembershipHost = {
  target_server_id: string;
  target_hostname: string | null;
  members: string[];
  primary_members: string[];
  supplementary_members: string[];
  error: string | null;
};

export type GroupMembership = {
  group: string;
  hosts: GroupMembershipHost[];
};

export type SSHKey = {
  id: string;
  name: string;
  public_key: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type PermissionTemplate = {
  id: string;
  path: string;
  owner: string | null;
  group: string | null;
  mode: string | null;
  recursive: boolean;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type AccessProfile = {
  id: string;
  name: string;
  description: string;
  shell: string;
  sudo_enabled: boolean;
  sudo_nopasswd: boolean;
  supplementary_groups: string[];
  permission_presets: string[];
  advanced: boolean;
};

export type GroupPreset = {
  id: string;
  name: string;
  group: string;
  description: string;
  recommended_for: string;
  distro_families: string[];
};

export type PermissionPreset = {
  id: string;
  name: string;
  mode: string;
  description: string;
  owner: string | null;
  group: string | null;
  recursive: boolean;
};

export type DiscoveredGroup = {
  name: string;
  hosts: string[];
  gid: number | null;
  members: string[];
};

export type DiscoveredUser = {
  username: string;
  hosts: string[];
  uid: number | null;
  gid: number | null;
  home_directory: string | null;
  shell: string | null;
};

export type IdentityMutationResponse<T> = {
  item: T;
  replication: BulkExecutionResponse | null;
};

export type CreateLinuxUserPayload = {
  username: string;
  shell: string;
  home_directory?: string | null;
  password_credential_ref?: string | null;
  sudo_enabled: boolean;
  sudo_nopasswd: boolean;
  locked: boolean;
  managed: boolean;
  supplementary_groups: string[];
  target_server_ids: string[];
};

export type UpdateLinuxUserPayload = Omit<CreateLinuxUserPayload, 'username'>;

export type CreateLinuxGroupPayload = {
  name: string;
  description?: string | null;
  managed: boolean;
  target_server_ids: string[];
  credential_ref?: string | null;
};

export type UpdateLinuxGroupPayload = CreateLinuxGroupPayload;

export type CreateSSHKeyPayload = {
  name: string;
  public_key: string;
  description?: string | null;
};

export type ApplyPermissionPayload = {
  path: string;
  owner?: string | null;
  group?: string | null;
  mode?: string | null;
  recursive: boolean;
  description?: string | null;
  target_server_ids: string[];
};
