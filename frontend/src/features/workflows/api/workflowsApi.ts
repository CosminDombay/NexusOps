import { apiClient } from '../../../lib/api/client';
import type { WorkflowRun } from '../types/workflow';

export async function listWorkflows(): Promise<WorkflowRun[]> {
  const response = await apiClient.get<WorkflowRun[]>('/workflows');
  return response.data;
}

export async function getWorkflow(workflowId: string): Promise<WorkflowRun> {
  const response = await apiClient.get<WorkflowRun>(`/workflows/${workflowId}`);
  return response.data;
}
