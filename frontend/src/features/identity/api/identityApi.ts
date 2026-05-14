import { apiClient } from '../../../lib/api/client';
import type { BulkExecutionResponse } from '../../jobs/types/job';
import type {
  AccessProfile,
  ApplyPermissionPayload,
  CreateLinuxGroupPayload,
  CreateLinuxUserPayload,
  DiscoveredGroup,
  GroupPreset,
  CreateSSHKeyPayload,
  IdentityMutationResponse,
  LinuxGroup,
  LinuxUser,
  PermissionTemplate,
  PermissionPreset,
  SSHKey,
} from '../types/identity';

export async function listAccessProfiles(): Promise<AccessProfile[]> {
  const response = await apiClient.get<AccessProfile[]>('/identity/access-profiles');
  return response.data;
}

export async function listLinuxUsers(): Promise<LinuxUser[]> {
  const response = await apiClient.get<LinuxUser[]>('/identity/users');
  return response.data;
}

export async function createLinuxUser(payload: CreateLinuxUserPayload): Promise<IdentityMutationResponse<LinuxUser>> {
  const response = await apiClient.post<IdentityMutationResponse<LinuxUser>>('/identity/users', payload);
  return response.data;
}

export async function replicateLinuxUser(userId: string, targetServerIds: string[]): Promise<BulkExecutionResponse> {
  const response = await apiClient.post<BulkExecutionResponse>(`/identity/users/${userId}/replicate`, {
    target_server_ids: targetServerIds,
  });
  return response.data;
}

export async function lockLinuxUser(userId: string, targetServerIds: string[]): Promise<BulkExecutionResponse> {
  const response = await apiClient.post<BulkExecutionResponse>(`/identity/users/${userId}/lock`, {
    target_server_ids: targetServerIds,
  });
  return response.data;
}

export async function unlockLinuxUser(userId: string, targetServerIds: string[]): Promise<BulkExecutionResponse> {
  const response = await apiClient.post<BulkExecutionResponse>(`/identity/users/${userId}/unlock`, {
    target_server_ids: targetServerIds,
  });
  return response.data;
}

export async function listLinuxGroups(): Promise<LinuxGroup[]> {
  const response = await apiClient.get<LinuxGroup[]>('/identity/groups');
  return response.data;
}

export async function listGroupPresets(): Promise<GroupPreset[]> {
  const response = await apiClient.get<GroupPreset[]>('/identity/groups/presets');
  return response.data;
}

export async function discoverGroups(targetServerIds: string[]): Promise<DiscoveredGroup[]> {
  const params = new URLSearchParams();
  targetServerIds.forEach((serverId) => params.append('target_server_ids', serverId));
  const response = await apiClient.get<{ groups: DiscoveredGroup[] }>(`/identity/groups/discover?${params.toString()}`);
  return response.data.groups;
}

export async function createLinuxGroup(payload: CreateLinuxGroupPayload): Promise<IdentityMutationResponse<LinuxGroup>> {
  const response = await apiClient.post<IdentityMutationResponse<LinuxGroup>>('/identity/groups', payload);
  return response.data;
}

export async function replicateLinuxGroup(groupId: string, targetServerIds: string[]): Promise<BulkExecutionResponse> {
  const response = await apiClient.post<BulkExecutionResponse>(`/identity/groups/${groupId}/replicate`, {
    target_server_ids: targetServerIds,
  });
  return response.data;
}

export async function addGroupMembers(
  groupId: string,
  usernames: string[],
  targetServerIds: string[],
): Promise<BulkExecutionResponse> {
  const response = await apiClient.post<BulkExecutionResponse>(`/identity/groups/${groupId}/members`, {
    usernames,
    target_server_ids: targetServerIds,
  });
  return response.data;
}

export async function listSSHKeys(): Promise<SSHKey[]> {
  const response = await apiClient.get<SSHKey[]>('/identity/ssh-keys');
  return response.data;
}

export async function createSSHKey(payload: CreateSSHKeyPayload): Promise<SSHKey> {
  const response = await apiClient.post<SSHKey>('/identity/ssh-keys', payload);
  return response.data;
}

export async function deploySSHKey(keyId: string, username: string, targetServerIds: string[]): Promise<BulkExecutionResponse> {
  const response = await apiClient.post<BulkExecutionResponse>(`/identity/ssh-keys/${keyId}/deploy`, {
    username,
    target_server_ids: targetServerIds,
  });
  return response.data;
}

export async function revokeSSHKey(keyId: string, username: string, targetServerIds: string[]): Promise<BulkExecutionResponse> {
  const response = await apiClient.post<BulkExecutionResponse>(`/identity/ssh-keys/${keyId}/revoke`, {
    username,
    target_server_ids: targetServerIds,
  });
  return response.data;
}

export async function listPermissionTemplates(): Promise<PermissionTemplate[]> {
  const response = await apiClient.get<PermissionTemplate[]>('/identity/permissions');
  return response.data;
}

export async function listPermissionPresets(): Promise<PermissionPreset[]> {
  const response = await apiClient.get<PermissionPreset[]>('/identity/permissions/presets');
  return response.data;
}

export async function applyPermission(payload: ApplyPermissionPayload): Promise<BulkExecutionResponse> {
  const response = await apiClient.post<BulkExecutionResponse>('/identity/permissions/apply', payload);
  return response.data;
}
