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
};

export type NodeRuntimeState = {
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
  degraded_reasons: string[];
  stale_reasons: string[];
  warnings: string[];
  last_checked_at: string | null;
  stale_after: string | null;
};
