import { apiClient } from '../../../lib/api/client';
import type {
  CreateServerPayload,
  ImportProxmoxVmPayload,
  InventoryHealthCheckResult,
  InventoryHealthSummary,
  Server,
  UpdateServerPayload,
} from '../types/server';

export async function listServers(): Promise<Server[]> {
  const response = await apiClient.get<Server[]>('/servers');
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

export async function importProxmoxVm(payload: ImportProxmoxVmPayload): Promise<Server> {
  const response = await apiClient.post<Server>('/servers/sync/proxmox/import', payload);
  return response.data;
}

export async function reconcileProxmoxInventory(): Promise<Server[]> {
  const response = await apiClient.post<Server[]>('/servers/sync/proxmox/reconcile');
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
