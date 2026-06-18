import { apiClient } from '../../../lib/api/client';
import type { BulkExecutionResponse } from '../../jobs/types/job';
import type {
  AccessProfile,
  ApplyPermissionPayload,
  CreateLinuxGroupPayload,
  CreateLinuxUserPayload,
  DiscoveredUser,
  DiscoveredGroup,
  GroupPreset,
  GroupMembership,
  CreateSSHKeyPayload,
  IdentityMutationResponse,
  LinuxGroup,
  LinuxUser,
  PermissionTemplate,
  PermissionTemplatePayload,
  PermissionPreset,
  SSHKey,
  UpdateSSHKeyPayload,
  UpdateLinuxUserPayload,
  UpdateLinuxGroupPayload,
  UserGroupMembership,
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

export async function adoptLinuxUser(payload: CreateLinuxUserPayload): Promise<IdentityMutationResponse<LinuxUser>> {
  const response = await apiClient.post<IdentityMutationResponse<LinuxUser>>('/identity/users/adopt', payload);
  return response.data;
}

export async function updateLinuxUser(userId: string, payload: UpdateLinuxUserPayload): Promise<IdentityMutationResponse<LinuxUser>> {
  const response = await apiClient.put<IdentityMutationResponse<LinuxUser>>(`/identity/users/${userId}`, payload);
  return response.data;
}

export async function discoverUsers(targetServerIds: string[]): Promise<DiscoveredUser[]> {
  const params = new URLSearchParams();
  targetServerIds.forEach((serverId) => params.append('target_server_ids', serverId));
  const response = await apiClient.get<{ users: DiscoveredUser[] }>(`/identity/users/discover?${params.toString()}`);
  return response.data.users;
}

export async function discoverUserGroups(username: string, targetServerIds: string[]): Promise<UserGroupMembership> {
  const params = new URLSearchParams();
  targetServerIds.forEach((serverId) => params.append('target_server_ids', serverId));
  const response = await apiClient.get<UserGroupMembership>(`/identity/users/${encodeURIComponent(username)}/groups?${params.toString()}`);
  return response.data;
}

function replicationPayload(targetServerIds: string[], credentialRef?: string | null) {
  return {
    target_server_ids: targetServerIds,
    credential_ref: credentialRef || null,
  };
}

export async function replicateLinuxUser(userId: string, targetServerIds: string[], credentialRef?: string | null): Promise<BulkExecutionResponse> {
  const response = await apiClient.post<BulkExecutionResponse>(`/identity/users/${userId}/replicate`, {
    ...replicationPayload(targetServerIds, credentialRef),
  });
  return response.data;
}

export async function lockLinuxUser(userId: string, targetServerIds: string[], credentialRef?: string | null): Promise<BulkExecutionResponse> {
  const response = await apiClient.post<BulkExecutionResponse>(`/identity/users/${userId}/lock`, {
    ...replicationPayload(targetServerIds, credentialRef),
  });
  return response.data;
}

export async function unlockLinuxUser(userId: string, targetServerIds: string[], credentialRef?: string | null): Promise<BulkExecutionResponse> {
  const response = await apiClient.post<BulkExecutionResponse>(`/identity/users/${userId}/unlock`, {
    ...replicationPayload(targetServerIds, credentialRef),
  });
  return response.data;
}

export async function expireLinuxUserPassword(userId: string, targetServerIds: string[], credentialRef?: string | null): Promise<BulkExecutionResponse> {
  const response = await apiClient.post<BulkExecutionResponse>(`/identity/users/${userId}/expire-password`, {
    ...replicationPayload(targetServerIds, credentialRef),
  });
  return response.data;
}

export async function disableLinuxUserShell(userId: string, targetServerIds: string[], credentialRef?: string | null): Promise<BulkExecutionResponse> {
  const response = await apiClient.post<BulkExecutionResponse>(`/identity/users/${userId}/disable-shell`, {
    ...replicationPayload(targetServerIds, credentialRef),
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

export async function discoverGroupMembers(groupName: string, targetServerIds: string[]): Promise<GroupMembership> {
  const params = new URLSearchParams();
  targetServerIds.forEach((serverId) => params.append('target_server_ids', serverId));
  const response = await apiClient.get<GroupMembership>(`/identity/groups/${encodeURIComponent(groupName)}/members/discover?${params.toString()}`);
  return response.data;
}

export async function createLinuxGroup(payload: CreateLinuxGroupPayload): Promise<IdentityMutationResponse<LinuxGroup>> {
  const response = await apiClient.post<IdentityMutationResponse<LinuxGroup>>('/identity/groups', payload);
  return response.data;
}

export async function adoptLinuxGroup(payload: CreateLinuxGroupPayload): Promise<IdentityMutationResponse<LinuxGroup>> {
  const response = await apiClient.post<IdentityMutationResponse<LinuxGroup>>('/identity/groups/adopt', payload);
  return response.data;
}

export async function updateLinuxGroup(groupId: string, payload: UpdateLinuxGroupPayload): Promise<IdentityMutationResponse<LinuxGroup>> {
  const response = await apiClient.put<IdentityMutationResponse<LinuxGroup>>(`/identity/groups/${groupId}`, payload);
  return response.data;
}

export async function deleteLinuxGroup(groupId: string, targetServerIds: string[] = []): Promise<void> {
  await apiClient.delete(`/identity/groups/${groupId}`, { data: targetServerIds });
}

export async function deleteLinuxUser(userId: string, targetServerIds: string[] = [], removeHome = false): Promise<void> {
  await apiClient.delete(`/identity/users/${userId}`, {
    params: { remove_home: removeHome },
    data: targetServerIds,
  });
}

export async function replicateLinuxGroup(groupId: string, targetServerIds: string[], credentialRef?: string | null): Promise<BulkExecutionResponse> {
  const response = await apiClient.post<BulkExecutionResponse>(`/identity/groups/${groupId}/replicate`, {
    ...replicationPayload(targetServerIds, credentialRef),
  });
  return response.data;
}

export async function addGroupMembers(
  groupId: string,
  usernames: string[],
  targetServerIds: string[],
  credentialRef?: string | null,
): Promise<BulkExecutionResponse> {
  const response = await apiClient.post<BulkExecutionResponse>(`/identity/groups/${groupId}/members`, {
    usernames,
    ...replicationPayload(targetServerIds, credentialRef),
  });
  return response.data;
}

export async function removeGroupMembers(
  groupId: string,
  usernames: string[],
  targetServerIds: string[],
  credentialRef?: string | null,
): Promise<BulkExecutionResponse> {
  const response = await apiClient.delete<BulkExecutionResponse>(`/identity/groups/${groupId}/members`, {
    data: {
      usernames,
      ...replicationPayload(targetServerIds, credentialRef),
    },
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

export async function updateSSHKey(keyId: string, payload: UpdateSSHKeyPayload): Promise<SSHKey> {
  const response = await apiClient.put<SSHKey>(`/identity/ssh-keys/${keyId}`, payload);
  return response.data;
}

export async function deploySSHKey(keyId: string, username: string, targetServerIds: string[]): Promise<BulkExecutionResponse> {
  const response = await apiClient.post<BulkExecutionResponse>(`/identity/ssh-keys/${keyId}/deploy`, {
    username: username || null,
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

export async function createPermissionTemplate(payload: PermissionTemplatePayload): Promise<PermissionTemplate> {
  const response = await apiClient.post<PermissionTemplate>('/identity/permissions', payload);
  return response.data;
}

export async function updatePermissionTemplate(templateId: string, payload: PermissionTemplatePayload): Promise<PermissionTemplate> {
  const response = await apiClient.put<PermissionTemplate>(`/identity/permissions/${templateId}`, payload);
  return response.data;
}

export async function replicatePermissionTemplate(templateId: string, targetServerIds: string[]): Promise<BulkExecutionResponse> {
  const response = await apiClient.post<BulkExecutionResponse>(`/identity/permissions/${templateId}/replicate`, {
    target_server_ids: targetServerIds,
  });
  return response.data;
}
