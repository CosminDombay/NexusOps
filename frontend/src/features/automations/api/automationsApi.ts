import { apiClient } from '../../../lib/api/client';
import type { Automation, AutomationPayload, AutomationRunResult } from '../types/automation';

export async function listAutomations(): Promise<Automation[]> {
  const response = await apiClient.get<Automation[]>('/automations');
  return response.data;
}

export async function createAutomation(payload: AutomationPayload): Promise<Automation> {
  const response = await apiClient.post<Automation>('/automations', payload);
  return response.data;
}

export async function updateAutomation(automationId: string, payload: Partial<AutomationPayload>): Promise<Automation> {
  const response = await apiClient.put<Automation>(`/automations/${automationId}`, payload);
  return response.data;
}

export async function deleteAutomation(automationId: string): Promise<void> {
  await apiClient.delete(`/automations/${automationId}`);
}

export async function enableAutomation(automationId: string): Promise<Automation> {
  const response = await apiClient.post<Automation>(`/automations/${automationId}/enable`);
  return response.data;
}

export async function disableAutomation(automationId: string): Promise<Automation> {
  const response = await apiClient.post<Automation>(`/automations/${automationId}/disable`);
  return response.data;
}

export async function runAutomation(automationId: string): Promise<AutomationRunResult> {
  const response = await apiClient.post<AutomationRunResult>(`/automations/${automationId}/run`);
  return response.data;
}
