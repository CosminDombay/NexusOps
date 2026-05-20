export type WorkflowStatus = 'pending' | 'queued' | 'running' | 'success' | 'failed' | 'cancelled';

export type WorkflowStepStatus = 'pending' | 'running' | 'success' | 'failed' | 'skipped';

export type WorkflowStep = {
  id: string;
  workflow_run_id: string;
  step_order: number;
  step_type: string;
  name: string;
  status: WorkflowStepStatus;
  started_at: string | null;
  finished_at: string | null;
  log_output: string;
  error_output: string;
  metadata_json: Record<string, unknown>;
  target_hostname: string | null;
  created_at: string;
  updated_at: string;
};

export type WorkflowRun = {
  id: string;
  workflow_type: string;
  status: WorkflowStatus;
  trigger_source: string;
  started_at: string | null;
  finished_at: string | null;
  target_server_id: string | null;
  target_hostname: string | null;
  initiated_by: string | null;
  context_json: Record<string, unknown>;
  result_summary: Record<string, unknown>;
  error_message: string | null;
  steps: WorkflowStep[];
  current_step: string | null;
  completed_steps: number;
  failed_steps: number;
  duration_seconds: number | null;
  target_nodes: string[];
  linked_job_ids: string[];
  created_at: string;
  updated_at: string;
};
