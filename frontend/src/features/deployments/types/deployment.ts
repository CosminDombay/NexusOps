import type { Job } from '../../jobs/types/job';

export type DeploymentStatus = 'draft' | 'deploying' | 'running' | 'stopped' | 'failed' | 'created' | 'deployed';

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
  job: Job;
};

export type DeploymentLogs = {
  deployment_id: string;
  target_server_id: string;
  logs: string;
  job: Job;
};

export type DeploymentStatusResult = {
  deployment_id: string;
  target_server_id: string;
  job: Job;
};
