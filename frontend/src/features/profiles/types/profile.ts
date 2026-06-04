import type { Job } from '../../jobs/types/job';

export type ProfileStep = {
  id: string;
  name: string;
  kind: 'action' | 'package' | 'command' | 'deployment' | 'script';
  reference_id: string;
  type?: 'action' | 'package' | 'deployment' | 'script' | null;
  target?: string | null;
  enabled?: boolean;
  credential_ref?: string | null;
  command?: string | null;
};

export type TemplateVariable = {
  name: string;
  description: string;
  default_value: string | null;
  required: boolean;
  sensitive: boolean;
  credential_type?: string | null;
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
  credential_refs?: Record<string, string>;
  execution_credential_ref?: string | null;
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
  credential_refs?: Record<string, string>;
  execution_credential_ref?: string | null;
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
