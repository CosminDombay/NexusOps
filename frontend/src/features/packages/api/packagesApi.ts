import { apiClient } from '../../../lib/api/client';
import type {
  CreatePackageDefinitionPayload,
  PackageDefinition,
  PackageDefinitionExport,
  PackageDefinitionImportResult,
  UpdatePackageDefinitionPayload,
} from '../types/package';
import type { BulkExecutionResponse, Job } from '../../jobs/types/job';

export async function listPackageDefinitions(): Promise<PackageDefinition[]> {
  const response = await apiClient.get<PackageDefinition[]>('/packages');
  return response.data;
}

export async function createPackageDefinition(
  payload: CreatePackageDefinitionPayload,
): Promise<PackageDefinition> {
  const response = await apiClient.post<PackageDefinition>('/packages', payload);
  return response.data;
}

export async function updatePackageDefinition(
  packageId: string,
  payload: Partial<UpdatePackageDefinitionPayload>,
): Promise<PackageDefinition> {
  const response = await apiClient.put<PackageDefinition>(`/packages/${packageId}`, payload);
  return response.data;
}

export async function clonePackageDefinition(
  packageId: string,
  payload: { id: string; name?: string },
): Promise<PackageDefinition> {
  const response = await apiClient.post<PackageDefinition>(`/packages/${packageId}/clone`, payload);
  return response.data;
}

export async function resetPackageDefinition(packageId: string): Promise<PackageDefinition> {
  const response = await apiClient.post<PackageDefinition>(`/packages/${packageId}/reset`);
  return response.data;
}

export async function deletePackageDefinition(packageId: string): Promise<void> {
  await apiClient.delete(`/packages/${packageId}`);
}

export async function exportPackageDefinition(
  packageId: string,
  format: 'json' | 'yaml' = 'json',
): Promise<PackageDefinitionExport> {
  const response = await apiClient.get<PackageDefinitionExport>(`/packages/${packageId}/export`, {
    params: { format },
  });
  return response.data;
}

export async function importPackageDefinition(
  content: string,
  format: 'json' | 'yaml',
  strategy: 'create' | 'clone_on_conflict' = 'clone_on_conflict',
): Promise<PackageDefinitionImportResult> {
  const response = await apiClient.post<PackageDefinitionImportResult>('/packages/import', {
    content,
    format,
    strategy,
  });
  return response.data;
}

export async function executePackageDefinition(
  packageId: string,
  targetServerId: string,
  operation: 'install' | 'uninstall' = 'install',
  variables: Record<string, string> = {},
  credentialRefs: Record<string, string> = {},
  executionCredentialRef: string | null = null,
): Promise<Job> {
  const response = await apiClient.post<Job>(`/packages/${packageId}/execute`, {
    target_server_id: targetServerId,
    operation,
    variables,
    credential_refs: credentialRefs,
    execution_credential_ref: executionCredentialRef,
  });
  return response.data;
}

export async function executePackageDefinitionBulk(
  packageId: string,
  targetServerIds: string[],
  operation: 'install' | 'uninstall' = 'install',
  variables: Record<string, string> = {},
  credentialRefs: Record<string, string> = {},
  executionCredentialRef: string | null = null,
): Promise<BulkExecutionResponse> {
  const response = await apiClient.post<BulkExecutionResponse>('/packages/apply/bulk', {
    package_id: packageId,
    target_server_ids: targetServerIds,
    operation,
    variables,
    credential_refs: credentialRefs,
    execution_credential_ref: executionCredentialRef,
  });
  return response.data;
}
