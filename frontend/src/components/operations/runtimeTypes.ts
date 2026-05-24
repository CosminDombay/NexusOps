export type OperationalActivity = {
  id: string;
  source_type: string;
  source_id: string;
  event_type: string;
  title: string;
  status: string | null;
  severity: 'info' | 'success' | 'warning' | 'danger' | string;
  occurred_at: string | null;
  message: string | null;
  correlation_id: string | null;
  job_ids: string[];
  metadata: Record<string, unknown>;
};
