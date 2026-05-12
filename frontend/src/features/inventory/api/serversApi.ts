import { apiClient } from '../../../lib/api/client';
import type { CreateServerPayload, Server } from '../types/server';

export async function listServers(): Promise<Server[]> {
  const response = await apiClient.get<Server[]>('/servers');
  return response.data;
}

export async function createServer(payload: CreateServerPayload): Promise<Server> {
  const response = await apiClient.post<Server>('/servers', payload);
  return response.data;
}
