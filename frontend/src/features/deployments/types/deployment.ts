import type { Job } from '../../jobs/types/job';

export type DeploymentStatus = 'draft' | 'deploying' | 'running' | 'stopped' | 'failed';

export type Deployment = {
  id: string;
  name: string;
  description: string | null;
  compose_content: string;
  env_content: string | null;
  status: DeploymentStatus;
  target_server_id: string | null;
  target_hostname: string | null;
  remote_path: string | null;
  created_at: string;
  updated_at: string;
};

export type CreateDeploymentPayload = {
  name: string;
  description?: string | null;
  target_server_id: string;
  compose_content: string;
  env_content?: string | null;
  remote_path?: string;
};

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
