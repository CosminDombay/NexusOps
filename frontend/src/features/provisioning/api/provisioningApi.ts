import { apiClient } from '../../../lib/api/client';
import type { CreateProvisioningPayload, ProxmoxTemplate, ProvisioningRequest } from '../types/provisioning';

export async function listProvisioningRequests(): Promise<ProvisioningRequest[]> {
  const response = await apiClient.get<ProvisioningRequest[]>('/vms');
  return response.data;
}

export async function listProxmoxTemplates(): Promise<ProxmoxTemplate[]> {
  const response = await apiClient.get<ProxmoxTemplate[]>('/vms/templates');
  return response.data;
}

export async function createProvisioningRequest(
  payload: CreateProvisioningPayload,
): Promise<ProvisioningRequest> {
  const response = await apiClient.post<ProvisioningRequest>('/vms', payload);
  return response.data;
}
