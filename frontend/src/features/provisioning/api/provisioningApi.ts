import { apiClient } from '../../../lib/api/client';
import type {
  CreateProvisioningBlueprintPayload,
  CreateProvisioningBootstrapTemplatePayload,
  CreateProvisioningBatchPayload,
  CreateProvisioningPayload,
  ProxmoxStorage,
  ProxmoxTemplate,
  ProvisioningBlueprint,
  ProvisioningBootstrapTemplate,
  ProvisioningBatch,
  ProvisioningCleanupResult,
  ProvisioningRequest,
  UpdateProvisioningBlueprintPayload,
  UpdateProvisioningBootstrapTemplatePayload,
} from '../types/provisioning';

export async function listProvisioningRequests(): Promise<ProvisioningRequest[]> {
  const response = await apiClient.get<ProvisioningRequest[]>('/vms');
  return response.data;
}

export async function listProvisioningBatches(): Promise<ProvisioningBatch[]> {
  const response = await apiClient.get<ProvisioningBatch[]>('/vms/batches');
  return response.data;
}

export async function createProvisioningBatch(
  payload: CreateProvisioningBatchPayload,
): Promise<ProvisioningBatch> {
  const response = await apiClient.post<ProvisioningBatch>('/vms/batches', payload);
  return response.data;
}

export async function listProxmoxTemplates(): Promise<ProxmoxTemplate[]> {
  const response = await apiClient.get<ProxmoxTemplate[]>('/vms/templates');
  return response.data;
}

export async function listProxmoxStorage(nodeName?: string): Promise<ProxmoxStorage[]> {
  const response = await apiClient.get<ProxmoxStorage[]>('/proxmox/storage', {
    params: nodeName ? { node_name: nodeName } : undefined,
  });
  return response.data;
}

export async function createProvisioningRequest(
  payload: CreateProvisioningPayload,
): Promise<ProvisioningRequest> {
  const response = await apiClient.post<ProvisioningRequest>('/vms', payload);
  return response.data;
}

export async function deleteProvisioningRequest(requestId: string): Promise<void> {
  await apiClient.delete(`/vms/${requestId}`);
}

export async function sanitizeStaleProvisioningRequests(dryRun = false): Promise<ProvisioningCleanupResult> {
  const response = await apiClient.post<ProvisioningCleanupResult>('/vms/sanitize-stale', null, {
    params: { dry_run: dryRun },
  });
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

export async function updateProvisioningBlueprint(
  blueprintId: string,
  payload: UpdateProvisioningBlueprintPayload,
): Promise<ProvisioningBlueprint> {
  const response = await apiClient.put<ProvisioningBlueprint>(`/vms/blueprints/${blueprintId}`, payload);
  return response.data;
}

export async function deleteProvisioningBlueprint(blueprintId: string): Promise<void> {
  await apiClient.delete(`/vms/blueprints/${blueprintId}`);
}

export async function listProvisioningBootstrapTemplates(): Promise<ProvisioningBootstrapTemplate[]> {
  const response = await apiClient.get<ProvisioningBootstrapTemplate[]>('/vms/bootstrap-templates');
  return response.data;
}

export async function createProvisioningBootstrapTemplate(
  payload: CreateProvisioningBootstrapTemplatePayload,
): Promise<ProvisioningBootstrapTemplate> {
  const response = await apiClient.post<ProvisioningBootstrapTemplate>('/vms/bootstrap-templates', payload);
  return response.data;
}

export async function updateProvisioningBootstrapTemplate(
  templateId: string,
  payload: UpdateProvisioningBootstrapTemplatePayload,
): Promise<ProvisioningBootstrapTemplate> {
  const response = await apiClient.put<ProvisioningBootstrapTemplate>(`/vms/bootstrap-templates/${templateId}`, payload);
  return response.data;
}

export async function deleteProvisioningBootstrapTemplate(templateId: string): Promise<void> {
  await apiClient.delete(`/vms/bootstrap-templates/${templateId}`);
}
