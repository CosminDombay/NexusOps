import { apiClient } from '../../../lib/api/client';
import type {
  CreateServerPayload,
  HostDocker,
  HostNetwork,
  HostSystem,
  ImportProxmoxVmPayload,
  InventoryHealthCheckResult,
  InventoryHealthSummary,
  Server,
  UpdateServerPayload,
} from '../types/server';

export type ServerListParams = {
  includeInactive?: boolean;
  integrationId?: string;
  cluster?: string;
};

export async function listServers(params: ServerListParams = {}): Promise<Server[]> {
  const response = await apiClient.get<Server[]>('/servers', {
    params: {
      ...(params.includeInactive ? { include_inactive: true } : {}),
      ...(params.integrationId ? { integration_id: params.integrationId } : {}),
      ...(params.cluster ? { cluster: params.cluster } : {}),
    },
  });
  return response.data;
}

export async function getServer(serverId: string): Promise<Server> {
  const response = await apiClient.get<Server>(`/servers/${serverId}`);
  return response.data;
}

export async function createServer(payload: CreateServerPayload): Promise<Server> {
  const response = await apiClient.post<Server>('/servers', payload);
  return response.data;
}

export async function updateServer(serverId: string, payload: UpdateServerPayload): Promise<Server> {
  const response = await apiClient.put<Server>(`/servers/${serverId}`, payload);
  return response.data;
}

export async function deleteServer(serverId: string): Promise<void> {
  await apiClient.delete(`/servers/${serverId}`);
}

export async function archiveServer(serverId: string): Promise<Server> {
  const response = await apiClient.post<Server>(`/servers/${serverId}/archive`);
  return response.data;
}

export async function decommissionServer(serverId: string): Promise<Server> {
  const response = await apiClient.post<Server>(`/servers/${serverId}/decommission`);
  return response.data;
}

export async function restoreServer(serverId: string): Promise<Server> {
  const response = await apiClient.post<Server>(`/servers/${serverId}/restore`);
  return response.data;
}

export async function unmanageServer(serverId: string): Promise<Server> {
  const response = await apiClient.post<Server>(`/servers/${serverId}/unmanage`);
  return response.data;
}

export async function importProxmoxVm(payload: ImportProxmoxVmPayload): Promise<Server> {
  const response = await apiClient.post<Server>('/servers/sync/proxmox/import', payload);
  return response.data;
}

export async function reconcileProxmoxInventory(integrationId: string): Promise<Server[]> {
  const response = await apiClient.post<Server[]>('/servers/sync/proxmox/reconcile', null, {
    params: { integration_id: integrationId },
  });
  return response.data;
}

export async function checkServerHealth(serverId: string): Promise<InventoryHealthCheckResult> {
  const response = await apiClient.post<InventoryHealthCheckResult>(`/servers/${serverId}/health-check`);
  return response.data;
}

export async function checkServersHealthBulk(serverIds?: string[]): Promise<InventoryHealthCheckResult[]> {
  const response = await apiClient.post<InventoryHealthCheckResult[]>('/servers/health-check/bulk', {
    server_ids: serverIds,
  });
  return response.data;
}

export async function getHealthSummary(): Promise<InventoryHealthSummary> {
  const response = await apiClient.get<InventoryHealthSummary>('/servers/health-summary');
  return response.data;
}

export async function getServerSystem(serverId: string): Promise<HostSystem> {
  const response = await apiClient.get<HostSystem>(`/servers/${serverId}/system`);
  return response.data;
}

export async function getServerNetwork(serverId: string): Promise<HostNetwork> {
  const response = await apiClient.get<HostNetwork>(`/servers/${serverId}/network`);
  return response.data;
}

export async function getServerDocker(serverId: string): Promise<HostDocker> {
  const response = await apiClient.get<HostDocker>(`/servers/${serverId}/docker`);
  return response.data;
}
