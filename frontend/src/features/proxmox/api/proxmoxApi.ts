import { apiClient } from '../../../lib/api/client';
import type { ProxmoxDashboard, ProxmoxNodeDetail, ProxmoxVmAction, ProxmoxVmActionResponse } from '../types/proxmox';

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
): Promise<ProxmoxVmActionResponse> {
  const response = await apiClient.post<ProxmoxVmActionResponse>(`/proxmox/vms/${vmId}/${action}`);
  return response.data;
}
