import { apiClient } from '../../../lib/api/client';
import type {
  ApplyProfilePayload,
  ApplyProfileBulkPayload,
  ApplyProfileBulkResult,
  ApplyProfileResult,
  CreateInfrastructureProfilePayload,
  InfrastructureProfile,
  InfrastructureProfileExport,
  InfrastructureProfileImportResult,
} from '../types/profile';

export async function listProfiles(): Promise<InfrastructureProfile[]> {
  const response = await apiClient.get<InfrastructureProfile[]>('/profiles');
  return response.data;
}

export async function applyProfile(
  profileId: string,
  payload: ApplyProfilePayload,
): Promise<ApplyProfileResult> {
  const response = await apiClient.post<ApplyProfileResult>(`/profiles/${profileId}/apply`, payload);
  return response.data;
}

export async function applyProfileBulk(payload: ApplyProfileBulkPayload): Promise<ApplyProfileBulkResult> {
  const response = await apiClient.post<ApplyProfileBulkResult>('/profiles/apply/bulk', payload);
  return response.data;
}

export async function createProfile(
  payload: CreateInfrastructureProfilePayload,
): Promise<InfrastructureProfile> {
  const response = await apiClient.post<InfrastructureProfile>('/profiles', payload);
  return response.data;
}

export async function updateProfile(
  profileId: string,
  payload: Partial<Omit<CreateInfrastructureProfilePayload, 'id'>>,
): Promise<InfrastructureProfile> {
  const response = await apiClient.put<InfrastructureProfile>(`/profiles/${profileId}`, payload);
  return response.data;
}

export async function cloneProfile(
  profileId: string,
  payload: { id: string; name?: string },
): Promise<InfrastructureProfile> {
  const response = await apiClient.post<InfrastructureProfile>(`/profiles/${profileId}/clone`, payload);
  return response.data;
}

export async function resetProfile(profileId: string): Promise<InfrastructureProfile> {
  const response = await apiClient.post<InfrastructureProfile>(`/profiles/${profileId}/reset`);
  return response.data;
}

export async function deleteProfile(profileId: string): Promise<void> {
  await apiClient.delete(`/profiles/${profileId}`);
}

export async function exportProfile(
  profileId: string,
  format: 'json' | 'yaml' = 'json',
): Promise<InfrastructureProfileExport> {
  const response = await apiClient.get<InfrastructureProfileExport>(`/profiles/${profileId}/export`, {
    params: { format },
  });
  return response.data;
}

export async function importProfile(
  content: string,
  format: 'json' | 'yaml',
  strategy: 'create' | 'clone_on_conflict' = 'clone_on_conflict',
): Promise<InfrastructureProfileImportResult> {
  const response = await apiClient.post<InfrastructureProfileImportResult>('/profiles/import', {
    content,
    format,
    strategy,
  });
  return response.data;
}
