import { apiClient } from '../../../lib/api/client';
import type { LoginRequest, LoginResponse } from '../types/auth';

export async function login(payload: LoginRequest): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>('/auth/login', payload);
  return response.data;
}

export async function refreshSession(refreshToken: string): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>('/auth/refresh', {
    refresh_token: refreshToken,
  });
  return response.data;
}

export async function logout(): Promise<void> {
  await apiClient.post('/auth/logout');
}

export async function getMe() {
  const response = await apiClient.get<LoginResponse['user']>('/auth/me');
  return response.data;
}
