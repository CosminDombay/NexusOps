import { apiClient } from '../../../lib/api/client';
import type {
  CreateProvisioningBlueprintPayload,
  CreateProvisioningPayload,
  ProxmoxTemplate,
  ProvisioningBlueprint,
  ProvisioningRequest,
} from '../types/provisioning';

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

export async function listProvisioningBlueprints(): Promise<ProvisioningBlueprint[]> {
  const response = await apiClient.get<ProvisioningBlueprint[]>('/vms/blueprints');
  return response.data;
}

export async function createProvisioningBlueprint(
  payload: CreateProvisioningBlueprintPayload,
): Promise<ProvisioningBlueprint> {
  const response = await apiClient.post<ProvisioningBlueprint>('/vms/blueprints', payload);
  return response.data;
}

export async function deleteProvisioningBlueprint(blueprintId: string): Promise<void> {
  await apiClient.delete(`/vms/blueprints/${blueprintId}`);
}
