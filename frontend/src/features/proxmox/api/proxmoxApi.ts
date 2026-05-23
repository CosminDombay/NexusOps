import { apiClient } from '../../../lib/api/client';
import type { ProxmoxDashboard, ProxmoxGuestSyncResult, ProxmoxHostSyncResult, ProxmoxNodeDetail, ProxmoxVmAction, ProxmoxVmActionResponse } from '../types/proxmox';

export async function getProxmoxDashboard(): Promise<ProxmoxDashboard> {
  const response = await apiClient.get<ProxmoxDashboard>('/proxmox/dashboard');
  return response.data;
}

export async function getProxmoxNodeDetail(nodeName: string): Promise<ProxmoxNodeDetail> {
  const response = await apiClient.get<ProxmoxNodeDetail>(`/proxmox/nodes/${encodeURIComponent(nodeName)}`);
  return response.data;
}

export async function runVmAction(
  vmId: number,
  action: ProxmoxVmAction,
  integrationId?: string | null,
): Promise<ProxmoxVmActionResponse> {
  const response = await apiClient.post<ProxmoxVmActionResponse>(`/proxmox/vms/${vmId}/${action}`, null, {
    params: integrationId ? { integration_id: integrationId } : undefined,
  });
  return response.data;
}

export async function syncProxmoxHosts(): Promise<ProxmoxHostSyncResult> {
  const response = await apiClient.post<ProxmoxHostSyncResult>('/proxmox/hosts/sync');
  return response.data;
}

export async function syncProxmoxGuests(): Promise<ProxmoxGuestSyncResult> {
  const response = await apiClient.post<ProxmoxGuestSyncResult>('/proxmox/guests/sync');
  return response.data;
}
