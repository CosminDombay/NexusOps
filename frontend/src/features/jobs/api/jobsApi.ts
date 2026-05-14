import { apiClient } from '../../../lib/api/client';
import type {
  BulkExecutionResponse,
  ExecuteActionPayload,
  ExecuteJobBulkPayload,
  ExecuteJobPayload,
  Job,
  OperationalAction,
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
