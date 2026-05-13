import { apiClient } from '../../../lib/api/client';
import type { CreatePackageDefinitionPayload, PackageDefinition } from '../types/package';
import type { Job } from '../../jobs/types/job';

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

export async function deletePackageDefinition(packageId: string): Promise<void> {
  await apiClient.delete(`/packages/${packageId}`);
}

export async function executePackageDefinition(
  packageId: string,
  targetServerId: string,
): Promise<Job> {
  const response = await apiClient.post<Job>(`/packages/${packageId}/execute`, {
    target_server_id: targetServerId,
  });
  return response.data;
}
