export type JobStatus = 'pending' | 'running' | 'success' | 'failed' | 'cancelled';

export type Job = {
  id: string;
  target_server_id: string;
  target_hostname: string | null;
  operation_type: string;
  command: string;
  status: JobStatus;
  stdout: string | null;
  stderr: string | null;
  exit_code: number | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ExecuteJobPayload = {
  target_server_id: string;
  command: string;
  operation_type: string;
};

export type BulkExecutionResult = {
  target_server_id: string;
  target_hostname: string | null;
  success: boolean;
  job: Job | null;
  error: string | null;
};

export type BulkExecutionResponse = {
  operation_type: string;
  success_count: number;
  failure_count: number;
  results: BulkExecutionResult[];
};

export type ExecuteJobBulkPayload = {
  target_server_ids: string[];
  command: string;
  operation_type: string;
};

export type OperationalAction = {
  id: string;
  name: string;
  category: string;
  description: string;
  command: string;
  destructive: boolean;
};

export type ExecuteActionPayload = {
  target_server_id: string;
  action_id: string;
};
