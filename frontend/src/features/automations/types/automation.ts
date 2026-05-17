import type { WorkflowRun } from '../../workflows/types/workflow';

export type Automation = {
  id: string;
  name: string;
  description: string | null;
  enabled: boolean;
  schedule_type: 'interval' | 'cron';
  cron_expression: string | null;
  interval_seconds: number | null;
  target_mode: 'single_host' | 'multiple_hosts';
  target_server_ids: string[];
  operation_type: 'action' | 'profile' | 'package' | 'deployment' | 'command';
  reference_id: string | null;
  raw_command: string | null;
  variables_json: Record<string, string>;
  credential_refs: Record<string, string>;
  last_run_at: string | null;
  next_run_at: string | null;
  last_status: string | null;
  created_at: string;
  updated_at: string;
};

export type AutomationPayload = {
  name: string;
  description?: string | null;
  enabled: boolean;
  schedule_type: 'interval' | 'cron';
  cron_expression?: string | null;
  interval_seconds?: number | null;
  target_mode: 'single_host' | 'multiple_hosts';
  target_server_ids: string[];
  operation_type: 'action' | 'profile' | 'package';
  reference_id: string;
  variables_json?: Record<string, string>;
  credential_refs?: Record<string, string>;
};

export type AutomationRunResult = WorkflowRun;
