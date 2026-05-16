import { apiClient } from '../../../lib/api/client';
import type { CreateCredentialPayload, Credential, UpdateCredentialPayload } from '../types/credential';

export async function listCredentials(): Promise<Credential[]> {
  const response = await apiClient.get<Credential[]>('/credentials');
  return response.data;
}

export async function createCredential(payload: CreateCredentialPayload): Promise<Credential> {
  const response = await apiClient.post<Credential>('/credentials', payload);
  return response.data;
}

export async function updateCredential(credentialId: string, payload: UpdateCredentialPayload): Promise<Credential> {
  const response = await apiClient.put<Credential>(`/credentials/${credentialId}`, payload);
  return response.data;
}

export async function deleteCredential(credentialId: string): Promise<void> {
  await apiClient.delete(`/credentials/${credentialId}`);
}
