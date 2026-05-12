import { apiClient } from '../../../lib/api/client';
import type { ProxmoxDashboard, ProxmoxVmAction, ProxmoxVmActionResponse } from '../types/proxmox';

export async function getProxmoxDashboard(): Promise<ProxmoxDashboard> {
  const response = await apiClient.get<ProxmoxDashboard>('/proxmox/dashboard');
  return response.data;
}

export async function runVmAction(
  vmId: number,
  action: ProxmoxVmAction,
): Promise<ProxmoxVmActionResponse> {
  const response = await apiClient.post<ProxmoxVmActionResponse>(`/proxmox/vms/${vmId}/${action}`);
  return response.data;
}
