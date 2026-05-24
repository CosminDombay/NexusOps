import { apiClient } from '../../../lib/api/client';
import type { WorkflowRun } from '../types/workflow';

export async function listWorkflows(filters: { targetServerId?: string } = {}): Promise<WorkflowRun[]> {
  const response = await apiClient.get<WorkflowRun[]>('/workflows', {
    params: filters.targetServerId ? { target_server_id: filters.targetServerId } : undefined,
  });
  return response.data;
}

export async function getWorkflow(workflowId: string): Promise<WorkflowRun> {
  const response = await apiClient.get<WorkflowRun>(`/workflows/${workflowId}`);
  return response.data;
}
