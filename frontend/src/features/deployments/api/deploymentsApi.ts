import { apiClient } from '../../../lib/api/client';
import type {
  CreateDeploymentPayload,
  Deployment,
  DeploymentDryRun,
  DeploymentExport,
  DeploymentImportResult,
  DeploymentLogs,
  DeploymentOperation,
  DeploymentStatusResult,
  UpdateDeploymentPayload,
} from '../types/deployment';

export async function listDeployments(filters: { serverId?: string } = {}): Promise<Deployment[]> {
  const response = await apiClient.get<Deployment[]>('/deployments', {
    params: filters.serverId ? { server_id: filters.serverId } : undefined,
  });
  return response.data;
}

export async function createDeployment(payload: CreateDeploymentPayload): Promise<Deployment> {
  const response = await apiClient.post<Deployment>('/deployments', payload);
  return response.data;
}

export async function deleteDeployment(deploymentId: string): Promise<void> {
  await apiClient.delete(`/deployments/${deploymentId}`);
}

export async function updateDeployment(deploymentId: string, payload: UpdateDeploymentPayload): Promise<Deployment> {
  const response = await apiClient.put<Deployment>(`/deployments/${deploymentId}`, payload);
  return response.data;
}

export async function exportDeployment(
  deploymentId: string,
  format: 'json' | 'yaml' = 'json',
): Promise<DeploymentExport> {
  const response = await apiClient.get<DeploymentExport>(`/deployments/${deploymentId}/export`, {
    params: { format },
  });
  return response.data;
}

export async function importDeployment(
  content: string,
  format: 'json' | 'yaml',
  strategy: 'create' | 'clone_on_conflict' = 'clone_on_conflict',
): Promise<DeploymentImportResult> {
  const response = await apiClient.post<DeploymentImportResult>('/deployments/import', {
    content,
    format,
    strategy,
  });
  return response.data;
}

export async function validateDeploymentPayload(
  payload: CreateDeploymentPayload,
  operation = 'deploy',
): Promise<DeploymentDryRun> {
  const response = await apiClient.post<DeploymentDryRun>('/deployments/validate', payload, {
    params: { operation },
  });
  return response.data;
}

export async function dryRunDeployment(deploymentId: string, operation = 'deploy'): Promise<DeploymentDryRun> {
  const response = await apiClient.get<DeploymentDryRun>(`/deployments/${deploymentId}/dry-run`, {
    params: { operation },
  });
  return response.data;
}

export async function runDeploymentOperation(
  deploymentId: string,
  operation: 'deploy' | 'redeploy' | 'restart' | 'stop',
): Promise<DeploymentOperation> {
  const response = await apiClient.post<DeploymentOperation>(`/deployments/${deploymentId}/${operation}`);
  return response.data;
}

export async function markDeploymentPlanned(deploymentId: string): Promise<Deployment> {
  const response = await apiClient.post<Deployment>(`/deployments/${deploymentId}/mark-planned`);
  return response.data;
}

export async function getDeploymentLogs(deploymentId: string): Promise<DeploymentLogs> {
  const response = await apiClient.get<DeploymentLogs>(`/deployments/${deploymentId}/logs`);
  return response.data;
}

export async function getDeploymentStatus(deploymentId: string): Promise<DeploymentStatusResult> {
  const response = await apiClient.get<DeploymentStatusResult>(`/deployments/${deploymentId}/status`);
  return response.data;
}

export async function refreshDeploymentRuntime(deploymentId: string): Promise<Deployment> {
  const response = await apiClient.post<Deployment>(`/deployments/${deploymentId}/refresh-runtime`);
  return response.data;
}
