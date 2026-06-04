import type { OperationalActivity } from '../../../components/operations/runtimeTypes';
import type { Job } from '../../jobs/types/job';

export type DeploymentStatus =
  | 'draft'
  | 'queued'
  | 'deploying'
  | 'running'
  | 'success'
  | 'partial_success'
  | 'degraded'
  | 'stopped'
  | 'failed'
  | 'cancelled'
  | 'created'
  | 'deployed';

export type DeploymentTargetExecution = {
  id: string;
  execution_id: string;
  deployment_id: string;
  target_id: string;
  server_id: string;
  hostname: string | null;
  status: DeploymentStatus;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  job_id: string | null;
  revision_id: string | null;
  stdout: string | null;
  stderr: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type DeploymentContainer = {
  service: string;
  name: string;
  state: string;
  health: string;
  uptime_seconds: number | null;
  restart_count: number | null;
};

export type DeploymentRuntimeState = {
  target_server_id: string;
  status: DeploymentStatus;
  runtime_state: string;
  sync_status: string;
  health_state: string;
  containers: DeploymentContainer[];
  missing_services: string[];
  inspected_at: string;
  error: string | null;
};

export type DeploymentExecution = {
  id: string;
  deployment_id: string;
  operation: string;
  status: DeploymentStatus;
  trigger_source: string;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  target_count: number;
  success_count: number;
  failed_count: number;
  result_summary: Record<string, unknown>;
  error_message: string | null;
  target_executions: DeploymentTargetExecution[];
  activity_timeline: OperationalActivity[];
  created_at: string;
  updated_at: string;
};

export type DeploymentTarget = {
  id: string;
  server_id: string;
  hostname: string | null;
  node_type: string | null;
  environment: string | null;
  provider: string | null;
  readiness: string;
  remote_path: string;
  status: DeploymentStatus;
  runtime_state: string;
  health_state: string;
  sync_status: string;
  runtime_checked_at: string | null;
  runtime_error: string | null;
  runtime_stale: boolean;
  runtime_age_seconds: number | null;
  runtime_failure_reason: string | null;
  containers: DeploymentContainer[];
  missing_services: string[];
  last_job_id: string | null;
  last_execution: DeploymentTargetExecution | null;
  created_at: string;
  updated_at: string;
};

export type Deployment = {
  id: string;
  name: string;
  description: string | null;
  compose_content: string;
  env_content: string | null;
  credential_refs: Record<string, string>;
  execution_credential_ref: string | null;
  status: DeploymentStatus;
  execution_status: DeploymentStatus | null;
  target_server_id: string | null;
  target_server_ids?: string[];
  target_hostname: string | null;
  targets: DeploymentTarget[];
  latest_execution: DeploymentExecution | null;
  execution_history: DeploymentExecution[];
  remote_path: string | null;
  ports: string[];
  compose_source: string;
  uptime_seconds: number | null;
  runtime_state: string;
  health_state: string;
  sync_status: string;
  runtime_checked_at: string | null;
  runtime_error: string | null;
  runtime_stale: boolean;
  runtime_age_seconds: number | null;
  runtime_failure_reason: string | null;
  created_at: string;
  updated_at: string;
};

export type CreateDeploymentPayload = {
  name: string;
  description?: string | null;
  target_server_id: string;
  target_server_ids?: string[];
  compose_content: string;
  env_content?: string | null;
  credential_refs?: Record<string, string>;
  execution_credential_ref?: string | null;
  remote_path?: string;
};

export type UpdateDeploymentPayload = CreateDeploymentPayload;

export type DeploymentOperation = {
  deployment: Deployment;
  job: Job | null;
  revision?: unknown | null;
  jobs: Job[];
  revisions?: unknown[];
  execution: DeploymentExecution | null;
};

export type DeploymentLogs = {
  deployment_id: string;
  target_server_id: string;
  logs: string;
  job: Job | null;
  jobs: Job[];
};

export type DeploymentStatusResult = {
  deployment_id: string;
  target_server_id: string | null;
  job: Job | null;
  jobs: Job[];
  runtime_states: DeploymentRuntimeState[];
};

export type DeploymentComposeValidation = {
  valid: boolean;
  errors: string[];
  warnings: string[];
  services: string[];
};

export type DeploymentDryRunTarget = {
  server_id: string;
  hostname: string | null;
  remote_path: string;
  deployment_path: string;
  execution_credential_ref: string | null;
  command_preview: string;
  redacted_command_preview: string;
};

export type DeploymentDryRun = {
  deployment_id: string | null;
  operation: string;
  validation: DeploymentComposeValidation;
  targets: DeploymentDryRunTarget[];
  env_keys: string[];
  credential_env_keys: string[];
};
