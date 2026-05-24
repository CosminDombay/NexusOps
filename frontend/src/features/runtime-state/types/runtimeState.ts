export type NodeRuntimeEligibility = {
  can_start: boolean;
  can_stop: boolean;
  can_reboot: boolean;
  can_open_shell: boolean;
  can_run_jobs: boolean;
  can_deploy: boolean;
  can_apply_profiles: boolean;
  can_manage_identity: boolean;
  can_monitor: boolean;
  can_sync_provider: boolean;
  blockers: Record<string, string[]>;
};

export type NodeRuntimeReconciliation = {
  provider_link_status: string;
  confidence: string;
  drift_indicators: string[];
  mismatch_explanations: string[];
  provider_sync_freshness: string;
  last_reconciled_at: string | null;
};

export type NodeRuntimeFreshness = {
  provider_refreshed_at: string | null;
  monitoring_refreshed_at: string | null;
  inventory_refreshed_at: string | null;
  runtime_refreshed_at: string | null;
  confidence: string;
};

export type NodeRuntimeState = {
  administrative_state: string;
  infrastructure_state: string;
  observability_state: string;
  inventory_state: string;
  provider_state: string;
  provider_reachable: boolean;
  provider_guest_exists: boolean;
  ssh_state: string;
  monitoring_state: string;
  readiness_state: string;
  orchestration_state: string;
  lifecycle_state: string;
  eligibility: NodeRuntimeEligibility;
  reconciliation: NodeRuntimeReconciliation;
  freshness: NodeRuntimeFreshness;
  degraded_reasons: string[];
  stale_reasons: string[];
  warnings: string[];
  last_checked_at: string | null;
  stale_after: string | null;
};
