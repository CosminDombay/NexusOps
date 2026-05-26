import { apiClient } from '../../../lib/api/client';
import type {
  RemoteDirectoryListing,
  RemoteFileRead,
  RemoteFileWriteRequest,
  RemoteFileWriteResponse,
} from '../types/remoteAccess';

type RemoteAccessTokenResponse = {
  token: string;
  expires_at: string;
};

export async function listRemoteFiles(serverId: string, path: string): Promise<RemoteDirectoryListing> {
  const response = await apiClient.get<RemoteDirectoryListing>(`/remote-access/hosts/${serverId}/files`, {
    params: { path },
  });
  return response.data;
}

export async function readRemoteFile(serverId: string, path: string): Promise<RemoteFileRead> {
  const response = await apiClient.get<RemoteFileRead>(`/remote-access/hosts/${serverId}/files/read`, {
    params: { path },
  });
  return response.data;
}

export async function writeRemoteFile(
  serverId: string,
  payload: RemoteFileWriteRequest,
): Promise<RemoteFileWriteResponse> {
  const response = await apiClient.put<RemoteFileWriteResponse>(
    `/remote-access/hosts/${serverId}/files/write`,
    payload,
  );
  return response.data;
}

export async function createShellToken(serverId: string): Promise<string> {
  const response = await apiClient.post<RemoteAccessTokenResponse>(`/remote-access/hosts/${serverId}/shell-token`);
  return response.data.token;
}

export function buildShellWebSocketUrl(serverId: string, token: string): string {
  const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
  const url = new URL(`${apiBase.replace(/\/$/, '')}/remote-access/hosts/${serverId}/shell`);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  url.searchParams.set('token', token);
  return url.toString();
}
