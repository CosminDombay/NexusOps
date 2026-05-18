import { apiClient } from '../../../lib/api/client';
import type { AuthUser, UserRole } from '../types/auth';

export type CreateUserPayload = {
  email: string;
  username: string;
  password: string;
  role: UserRole;
  is_active: boolean;
  is_superuser: boolean;
};

export type UpdateUserPayload = Partial<Omit<CreateUserPayload, 'password'>>;

export async function listUsers(): Promise<AuthUser[]> {
  const response = await apiClient.get<AuthUser[]>('/auth/users');
  return response.data;
}

export async function createUser(payload: CreateUserPayload): Promise<AuthUser> {
  const response = await apiClient.post<AuthUser>('/auth/users', payload);
  return response.data;
}

export async function updateUser(userId: string, payload: UpdateUserPayload): Promise<AuthUser> {
  const response = await apiClient.put<AuthUser>(`/auth/users/${userId}`, payload);
  return response.data;
}

export async function resetUserPassword(userId: string, password: string): Promise<AuthUser> {
  const response = await apiClient.post<AuthUser>(`/auth/users/${userId}/reset-password`, { password });
  return response.data;
}
