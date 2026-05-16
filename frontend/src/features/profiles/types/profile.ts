import type { Job } from '../../jobs/types/job';

export type ProfileStep = {
  id: string;
  name: string;
  kind: 'action' | 'package' | 'command';
  reference_id: string;
  command?: string | null;
};

export type TemplateVariable = {
  name: string;
  description: string;
  default_value: string | null;
  required: boolean;
  sensitive: boolean;
};

export type InfrastructureProfile = {
  id: string;
  name: string;
  category: string;
  description: string;
  tags: string[];
  steps: ProfileStep[];
  variables: TemplateVariable[];
  is_builtin: boolean;
  is_modified: boolean;
  base_version: string | null;
  source_template_id: string | null;
  modified_at: string | null;
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
  variables: TemplateVariable[];
};

export type ApplyProfilePayload = {
  target_server_id: string;
  stop_on_failure: boolean;
  variables?: Record<string, string>;
};

export type ApplyProfileResult = {
  profile_id: string;
  target_server_id: string;
  status: string;
  jobs: Job[];
  message: string;
};

export type ApplyProfileBulkPayload = {
  profile_id: string;
  target_server_ids: string[];
  stop_on_failure: boolean;
  variables?: Record<string, string>;
};

export type ApplyProfileBulkResult = {
  profile_id: string;
  success_count: number;
  failure_count: number;
  results: Array<{
    target_server_id: string;
    target_hostname: string | null;
    success: boolean;
    result: ApplyProfileResult | null;
    error: string | null;
  }>;
};
