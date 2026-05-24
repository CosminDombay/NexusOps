from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class NodeRuntimeEligibility(BaseModel):
    can_start: bool = False
    can_stop: bool = False
    can_reboot: bool = False
    can_open_shell: bool = False
    can_run_jobs: bool = False
    can_deploy: bool = False
    can_apply_profiles: bool = False
    can_manage_identity: bool = False
    can_monitor: bool = False
    can_sync_provider: bool = False
    blockers: dict[str, list[str]] = Field(default_factory=dict)


class NodeRuntimeReconciliation(BaseModel):
    provider_link_status: str = "unknown"
    confidence: str = "unknown"
    drift_indicators: list[str] = Field(default_factory=list)
    mismatch_explanations: list[str] = Field(default_factory=list)
    provider_sync_freshness: str = "unknown"
    last_reconciled_at: datetime | None = None


class NodeRuntimeFreshness(BaseModel):
    provider_refreshed_at: datetime | None = None
    monitoring_refreshed_at: datetime | None = None
    inventory_refreshed_at: datetime | None = None
    runtime_refreshed_at: datetime | None = None
    confidence: str = "unknown"


class NodeRuntimeState(BaseModel):
    administrative_state: str = "active"
    infrastructure_state: str = "unknown"
    observability_state: str = "missing"
    inventory_state: str = "unknown"
    provider_state: str = "unknown"
    provider_reachable: bool = False
    provider_guest_exists: bool = False
    ssh_state: str = "unknown"
    monitoring_state: str = "unknown"
    readiness_state: str = "unknown"
    orchestration_state: str = "unknown"
    lifecycle_state: str = "unknown"
    eligibility: NodeRuntimeEligibility = Field(default_factory=NodeRuntimeEligibility)
    reconciliation: NodeRuntimeReconciliation = Field(default_factory=NodeRuntimeReconciliation)
    freshness: NodeRuntimeFreshness = Field(default_factory=NodeRuntimeFreshness)
    degraded_reasons: list[str] = Field(default_factory=list)
    stale_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    last_checked_at: datetime | None = None
    stale_after: datetime | None = None


class RuntimeSnapshotRead(BaseModel):
    node_id: UUID
    runtime_state: NodeRuntimeState
    refresh_scope: str = "inventory"
    refresh_status: str = "unknown"
    last_error: str | None = None
    last_refresh_started_at: datetime | None = None
    last_refresh_finished_at: datetime | None = None


class RuntimeRefreshStatusRead(BaseModel):
    scope: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_error: str | None = None
    metadata_json: dict[str, object] = Field(default_factory=dict)
