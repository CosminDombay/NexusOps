import type { Job } from '../../jobs/types/job';

export type ProfileStep = {
  id: string;
  name: string;
  kind: 'action' | 'package';
  reference_id: string;
};

export type InfrastructureProfile = {
  id: string;
  name: string;
  category: string;
  description: string;
  tags: string[];
  steps: ProfileStep[];
  is_builtin: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type CreateInfrastructureProfilePayload = {
  id: string;
  name: string;
  category: string;
  description: string;
  tags: string[];
  steps: ProfileStep[];
};

export type ApplyProfilePayload = {
  target_server_id: string;
  stop_on_failure: boolean;
};

export type ApplyProfileResult = {
  profile_id: string;
  target_server_id: string;
  status: string;
  jobs: Job[];
  message: string;
};
