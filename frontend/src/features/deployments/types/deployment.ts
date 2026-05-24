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
  status: DeploymentStatus;
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
  health_state: string;
  sync_status: string;
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
};
