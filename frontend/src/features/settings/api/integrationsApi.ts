import { apiClient } from '../../../lib/api/client';
import type { ProxmoxHostSyncResult } from '../../proxmox/types/proxmox';
import type { Integration, IntegrationPayload, IntegrationTestResult } from '../types/integration';

export async function listIntegrations(): Promise<Integration[]> {
  const response = await apiClient.get<Integration[]>('/integrations');
  return response.data;
}

export async function createIntegration(payload: IntegrationPayload): Promise<Integration> {
  const response = await apiClient.post<Integration>('/integrations', payload);
  return response.data;
}

export async function updateIntegration(integrationId: string, payload: Partial<IntegrationPayload>): Promise<Integration> {
  const response = await apiClient.put<Integration>(`/integrations/${integrationId}`, payload);
  return response.data;
}

export async function deleteIntegration(integrationId: string): Promise<void> {
  await apiClient.delete(`/integrations/${integrationId}`);
}

export async function testIntegration(integrationId: string): Promise<IntegrationTestResult> {
  const response = await apiClient.post<IntegrationTestResult>(`/integrations/${integrationId}/test`);
  return response.data;
}

export async function syncProxmoxHostsForIntegration(integrationId: string): Promise<ProxmoxHostSyncResult> {
  const response = await apiClient.post<ProxmoxHostSyncResult>(`/integrations/${integrationId}/sync/proxmox-hosts`);
  return response.data;
}
