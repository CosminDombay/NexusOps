import { apiClient } from '../../../lib/api/client';
import type {
  BulkExecutionResponse,
  CreateOperationalActionPayload,
  ExecuteActionPayload,
  ExecuteJobBulkPayload,
  ExecuteJobPayload,
  Job,
  OperationalAction,
  UpdateOperationalActionPayload,
} from '../types/job';

export async function listJobs(): Promise<Job[]> {
  const response = await apiClient.get<Job[]>('/jobs');
  return response.data;
}

export async function executeJob(payload: ExecuteJobPayload): Promise<Job> {
  const response = await apiClient.post<Job>('/jobs/execute', payload);
  return response.data;
}

export async function executeJobBulk(payload: ExecuteJobBulkPayload): Promise<BulkExecutionResponse> {
  const response = await apiClient.post<BulkExecutionResponse>('/jobs/execute/bulk', payload);
  return response.data;
}

export async function listOperationalActions(): Promise<OperationalAction[]> {
  const response = await apiClient.get<OperationalAction[]>('/jobs/actions');
  return response.data;
}

export async function executeOperationalAction(payload: ExecuteActionPayload): Promise<Job> {
  const response = await apiClient.post<Job>('/jobs/actions/execute', payload);
  return response.data;
}

export async function createOperationalAction(payload: CreateOperationalActionPayload): Promise<OperationalAction> {
  const response = await apiClient.post<OperationalAction>('/jobs/actions', payload);
  return response.data;
}

export async function updateOperationalAction(actionId: string, payload: UpdateOperationalActionPayload): Promise<OperationalAction> {
  const response = await apiClient.put<OperationalAction>(`/jobs/actions/${actionId}`, payload);
  return response.data;
}

export async function deleteOperationalAction(actionId: string): Promise<void> {
  await apiClient.delete(`/jobs/actions/${actionId}`);
}
