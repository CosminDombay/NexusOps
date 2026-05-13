import { apiClient } from '../../../lib/api/client';
import type {
  ApplyProfilePayload,
  ApplyProfileResult,
  CreateInfrastructureProfilePayload,
  InfrastructureProfile,
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

export async function createProfile(
  payload: CreateInfrastructureProfilePayload,
): Promise<InfrastructureProfile> {
  const response = await apiClient.post<InfrastructureProfile>('/profiles', payload);
  return response.data;
}

export async function deleteProfile(profileId: string): Promise<void> {
  await apiClient.delete(`/profiles/${profileId}`);
}
