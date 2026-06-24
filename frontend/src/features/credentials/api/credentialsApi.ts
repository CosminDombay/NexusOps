import { apiClient } from '../../../lib/api/client';
import type { CreateCredentialPayload, Credential, CredentialUsage, UpdateCredentialPayload } from '../types/credential';

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

export async function deleteCredential(credentialId: string, reason?: string): Promise<Credential> {
  const response = await apiClient.delete<Credential>(`/credentials/${credentialId}`, {
    data: reason ? { reason } : undefined,
  });
  return response.data;
}

export async function getCredentialUsage(credentialId: string): Promise<CredentialUsage> {
  const response = await apiClient.get<CredentialUsage>(`/credentials/${credentialId}/usage`);
  return response.data;
}
