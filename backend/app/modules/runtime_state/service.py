from datetime import UTC, datetime
from typing import Any

from backend.app.common.constants import (
    InventoryHealthStatus,
    InventoryLifecycleState,
    InventorySyncStatus,
    ManagedNodeType,
    ManagementState,
)
from backend.app.modules.runtime_state.schemas import (
    NodeRuntimeEligibility,
    NodeRuntimeFreshness,
    NodeRuntimeReconciliation,
    NodeRuntimeState,
)

INACTIVE_LIFECYCLE_STATES = {
    InventoryLifecycleState.ARCHIVED.value,
    InventoryLifecycleState.DECOMMISSIONED.value,
    InventoryLifecycleState.DELETED.value,
}

EXECUTABLE_NODE_TYPES = {
    ManagedNodeType.VM.value,
    ManagedNodeType.LXC.value,
    ManagedNodeType.PHYSICAL.value,
    ManagedNodeType.HYPERVISOR.value,
}


class RuntimeStateService:
    """Derives normalized runtime state and action eligibility for managed nodes."""

    @classmethod
    def from_inventory_node(
        cls,
        server: Any,
        *,
        provider_state: str | None = None,
        provider_reachable: bool | None = None,
        provider_guest_exists: bool | None = None,
    ) -> NodeRuntimeState:
        inventory_state = cls._value(getattr(server, "lifecycle_state", None))
        management_state = cls._value(getattr(server, "management_state", None))
        sync_state = cls._value(getattr(server, "sync_state", None) or getattr(server, "sync_status", None))
        node_type = cls._value(getattr(server, "node_type", None))
        health_state = cls._value(getattr(server, "last_health_status", None))
        metadata = getattr(server, "provider_metadata", None)
        metadata = metadata if isinstance(metadata, dict) else {}

        inferred_provider_state = cls._provider_state_from_inventory(
            server,
            sync_state=sync_state,
            metadata=metadata,
        )
        provider_state = provider_state or inferred_provider_state
        provider_guest_exists = (
            provider_guest_exists
            if provider_guest_exists is not None
            else cls._provider_guest_exists_from_inventory(server, sync_state=sync_state)
        )
        provider_reachable = (
            provider_reachable
            if provider_reachable is not None
            else cls._provider_reachable_from_inventory(server, sync_state=sync_state, provider_guest_exists=provider_guest_exists)
        )

        ssh_state = cls._ssh_state(health_state, inventory_state, metadata)
        monitoring_state = cls._monitoring_state(metadata)
        orchestration_state = cls._orchestration_state(
            managed=bool(getattr(server, "managed", False)),
            management_state=management_state,
            inventory_state=inventory_state,
            node_type=node_type,
            ssh_state=ssh_state,
        )
        administrative_state = cls._administrative_state(inventory_state)
        infrastructure_state = cls._infrastructure_state(
            provider=cls._str(getattr(server, "provider", None)),
            provider_state=provider_state,
            provider_guest_exists=provider_guest_exists,
        )
        observability_state = cls._observability_state(monitoring_state)
        reconciliation = cls._reconciliation(
            server,
            provider=cls._str(getattr(server, "provider", None)),
            sync_state=sync_state,
            provider_guest_exists=provider_guest_exists,
            metadata=metadata,
        )
        freshness = cls._freshness(server, stale_reasons=cls._stale_reasons(server, sync_state=sync_state, metadata=metadata))

        eligibility = cls._eligibility(
            provider_state=provider_state,
            provider_reachable=provider_reachable,
            provider_guest_exists=provider_guest_exists,
            ssh_state=ssh_state,
            monitoring_state=monitoring_state,
            orchestration_state=orchestration_state,
            inventory_state=inventory_state,
            node_type=node_type,
            provider=cls._str(getattr(server, "provider", None)),
        )
        degraded_reasons = cls._degraded_reasons(
            provider=cls._str(getattr(server, "provider", None)),
            inventory_state=inventory_state,
            sync_state=sync_state,
            provider_reachable=provider_reachable,
            provider_guest_exists=provider_guest_exists,
            ssh_state=ssh_state,
            monitoring_state=monitoring_state,
            orchestration_state=orchestration_state,
        )
        stale_reasons = cls._stale_reasons(server, sync_state=sync_state, metadata=metadata)
        warnings = cls._warnings(
            server,
            node_type=node_type,
            provider_state=provider_state,
            provider_guest_exists=provider_guest_exists,
            ssh_state=ssh_state,
            monitoring_state=monitoring_state,
        )

        return NodeRuntimeState(
            administrative_state=administrative_state,
            infrastructure_state=infrastructure_state,
            observability_state=observability_state,
            inventory_state=inventory_state,
            provider_state=provider_state,
            provider_reachable=provider_reachable,
            provider_guest_exists=provider_guest_exists,
            ssh_state=ssh_state,
            monitoring_state=monitoring_state,
            orchestration_state=orchestration_state,
            lifecycle_state=inventory_state,
            eligibility=eligibility,
            reconciliation=reconciliation,
            freshness=freshness,
            degraded_reasons=list(dict.fromkeys(degraded_reasons)),
            stale_reasons=list(dict.fromkeys(stale_reasons)),
            warnings=list(dict.fromkeys(warnings)),
        )

    @classmethod
    def from_provider_guest(cls, vm: Any, inventory_node: Any | None = None) -> NodeRuntimeState:
        provider_state = cls._str(getattr(vm, "status", None), "unknown")
        provider_guest_exists = not bool(getattr(vm, "template", False))
        provider_reachable = provider_guest_exists
        if inventory_node is None:
            unmanaged = _ProviderGuestInventoryShim(vm)
            return cls.from_inventory_node(
                unmanaged,
                provider_state=provider_state,
                provider_reachable=provider_reachable,
                provider_guest_exists=provider_guest_exists,
            )
        return cls.from_inventory_node(
            inventory_node,
            provider_state=provider_state,
            provider_reachable=provider_reachable,
            provider_guest_exists=provider_guest_exists,
        )

    @staticmethod
    def _value(value: object, default: str = "unknown") -> str:
        if value is None:
            return default
        return str(getattr(value, "value", value))

    @staticmethod
    def _str(value: object, default: str = "") -> str:
        if value is None:
            return default
        return str(value)

    @classmethod
    def _provider_state_from_inventory(cls, server: Any, *, sync_state: str, metadata: dict[str, object]) -> str:
        if cls._str(getattr(server, "provider", None)).lower() != "proxmox":
            return "not_provider_backed"
        if sync_state == InventorySyncStatus.ORPHANED.value:
            return "guest_missing"
        if sync_state == InventorySyncStatus.UNKNOWN.value:
            return "unknown"
        state = cls._str(metadata.get("vm_status") or metadata.get("node_status") or metadata.get("operational_readiness"), "")
        if state:
            return state
        server_status = cls._value(getattr(server, "status", None), "")
        if server_status == "online":
            return "running"
        if server_status == "offline":
            return "stopped"
        return "linked"

    @classmethod
    def _provider_guest_exists_from_inventory(cls, server: Any, *, sync_state: str) -> bool:
        if cls._str(getattr(server, "provider", None)).lower() != "proxmox":
            return False
        if sync_state == InventorySyncStatus.ORPHANED.value:
            return False
        return bool(getattr(server, "vmid", None) or getattr(server, "external_id", None) or getattr(server, "provider_node", None))

    @classmethod
    def _provider_reachable_from_inventory(cls, server: Any, *, sync_state: str, provider_guest_exists: bool) -> bool:
        if cls._str(getattr(server, "provider", None)).lower() != "proxmox":
            return False
        return provider_guest_exists and sync_state not in {InventorySyncStatus.UNKNOWN.value, InventorySyncStatus.ORPHANED.value}

    @staticmethod
    def _ssh_state(health_state: str, inventory_state: str, metadata: dict[str, object]) -> str:
        if inventory_state in INACTIVE_LIFECYCLE_STATES:
            return "inactive"
        if health_state == InventoryHealthStatus.ONLINE.value:
            return "ready"
        if health_state == InventoryHealthStatus.UNREACHABLE.value:
            return "unreachable"
        if health_state == InventoryHealthStatus.PROVISIONING.value:
            return "provisioning"
        if health_state == InventoryHealthStatus.SYNC_ERROR.value:
            return "error"
        if metadata.get("ssh_ready") is False:
            return "unreachable"
        return "unknown"

    @staticmethod
    def _monitoring_state(metadata: dict[str, object]) -> str:
        state = metadata.get("monitoring_state")
        if isinstance(state, str) and state:
            return state
        if metadata.get("metrics_available") and metadata.get("logs_available"):
            return "monitoring_ready"
        if metadata.get("metrics_available") or metadata.get("logs_available"):
            return "monitoring_partial"
        if metadata.get("stale_metrics"):
            return "stale_metrics"
        return "unknown"

    @staticmethod
    def _orchestration_state(*, managed: bool, management_state: str, inventory_state: str, node_type: str, ssh_state: str) -> str:
        if inventory_state in INACTIVE_LIFECYCLE_STATES:
            return "inactive"
        if not managed or management_state != ManagementState.MANAGED.value:
            return "unmanaged"
        if node_type not in EXECUTABLE_NODE_TYPES:
            return "unsupported"
        if ssh_state == "ready":
            return "ready"
        return "blocked"

    @staticmethod
    def _readiness_state(*, ssh_state: str, monitoring_state: str, orchestration_state: str) -> str:
        if orchestration_state == "inactive":
            return "inactive"
        if orchestration_state == "ready" and monitoring_state == "monitoring_ready":
            return "ready"
        if orchestration_state == "ready":
            return "degraded"
        if ssh_state in {"unreachable", "error"}:
            return "degraded"
        if monitoring_state == "stale_metrics":
            return "stale"
        return "unknown"

    @staticmethod
    def _administrative_state(inventory_state: str) -> str:
        if inventory_state in {
            InventoryLifecycleState.ARCHIVED.value,
            InventoryLifecycleState.DECOMMISSIONED.value,
            InventoryLifecycleState.DELETED.value,
        }:
            return inventory_state
        return "active"

    @staticmethod
    def _infrastructure_state(*, provider: str, provider_state: str, provider_guest_exists: bool) -> str:
        if provider.lower() == "proxmox" and not provider_guest_exists:
            return "missing"
        if provider_state in {"running", "stopped"}:
            return provider_state
        return "unknown"

    @staticmethod
    def _observability_state(monitoring_state: str) -> str:
        if monitoring_state in {"monitoring_ready", "monitoring_partial", "stale_metrics"}:
            return monitoring_state
        return "missing"

    @classmethod
    def _eligibility(
        cls,
        *,
        provider_state: str,
        provider_reachable: bool,
        provider_guest_exists: bool,
        ssh_state: str,
        monitoring_state: str,
        orchestration_state: str,
        inventory_state: str,
        node_type: str,
        provider: str,
    ) -> NodeRuntimeEligibility:
        active = inventory_state not in INACTIVE_LIFECYCLE_STATES
        provider_lifecycle = active and provider.lower() == "proxmox" and provider_reachable and provider_guest_exists
        ssh_runtime = active and orchestration_state == "ready" and ssh_state == "ready"
        is_running = provider_state == "running"
        monitorable = active and monitoring_state not in {"disabled", "not_configured"}

        values = {
            "can_start": provider_lifecycle and not is_running,
            "can_stop": provider_lifecycle and is_running,
            "can_reboot": provider_lifecycle and is_running,
            "can_open_shell": ssh_runtime,
            "can_run_jobs": ssh_runtime,
            "can_deploy": ssh_runtime and node_type != ManagedNodeType.HYPERVISOR.value,
            "can_apply_profiles": ssh_runtime,
            "can_manage_identity": ssh_runtime,
            "can_monitor": monitorable,
            "can_sync_provider": active and provider.lower() == "proxmox",
        }
        blockers = {
            action: cls._eligibility_blockers(
                action=action,
                active=active,
                provider=provider,
                provider_reachable=provider_reachable,
                provider_guest_exists=provider_guest_exists,
                ssh_state=ssh_state,
                orchestration_state=orchestration_state,
                node_type=node_type,
                provider_state=provider_state,
            )
            for action, allowed in values.items()
            if not allowed
        }
        return NodeRuntimeEligibility(
            **values,
            blockers=blockers,
        )

    @staticmethod
    def _eligibility_blockers(
        *,
        action: str,
        active: bool,
        provider: str,
        provider_reachable: bool,
        provider_guest_exists: bool,
        ssh_state: str,
        orchestration_state: str,
        node_type: str,
        provider_state: str,
    ) -> list[str]:
        reasons: list[str] = []
        if not active:
            reasons.append("lifecycle_inactive")
        if action in {"can_start", "can_stop", "can_reboot", "can_sync_provider"}:
            if provider.lower() != "proxmox":
                reasons.append("provider_unsupported")
            if not provider_guest_exists:
                reasons.append("provider_guest_missing")
            if not provider_reachable:
                reasons.append("provider_unreachable")
            if action in {"can_stop", "can_reboot"} and provider_state != "running":
                reasons.append("provider_guest_not_running")
            if action == "can_start" and provider_state == "running":
                reasons.append("provider_guest_already_running")
        if action in {"can_open_shell", "can_run_jobs", "can_deploy", "can_apply_profiles", "can_manage_identity"}:
            if orchestration_state != "ready":
                reasons.append(f"orchestration_{orchestration_state}")
            if ssh_state != "ready":
                reasons.append(f"ssh_{ssh_state}")
        if action == "can_deploy" and node_type == ManagedNodeType.HYPERVISOR.value:
            reasons.append("hypervisor_deployments_unsupported")
        return list(dict.fromkeys(reasons or ["policy_not_satisfied"]))

    @staticmethod
    def _degraded_reasons(
        *,
        provider: str,
        inventory_state: str,
        sync_state: str,
        provider_reachable: bool,
        provider_guest_exists: bool,
        ssh_state: str,
        monitoring_state: str,
        orchestration_state: str,
    ) -> list[str]:
        reasons: list[str] = []
        has_provider_lifecycle = provider.lower() == "proxmox"
        if inventory_state in INACTIVE_LIFECYCLE_STATES:
            reasons.append(f"inventory_{inventory_state}")
        if has_provider_lifecycle and (sync_state == InventorySyncStatus.ORPHANED.value or not provider_guest_exists):
            reasons.append("provider_guest_missing")
        elif has_provider_lifecycle and not provider_reachable and sync_state != InventorySyncStatus.UNMANAGED.value:
            reasons.append("provider_unreachable")
        if ssh_state in {"unreachable", "error", "unknown"}:
            reasons.append(f"ssh_{ssh_state}")
        if monitoring_state in {"monitoring_missing", "monitoring_partial", "stale_metrics"}:
            reasons.append(monitoring_state)
        if orchestration_state in {"blocked", "unmanaged", "unsupported"}:
            reasons.append(f"orchestration_{orchestration_state}")
        return reasons

    @staticmethod
    def _stale_reasons(server: Any, *, sync_state: str, metadata: dict[str, object]) -> list[str]:
        reasons: list[str] = []
        if sync_state in {InventorySyncStatus.UNKNOWN.value, InventorySyncStatus.ORPHANED.value, InventorySyncStatus.MISMATCH.value}:
            reasons.append(f"sync_{sync_state}")
        last_seen_at = getattr(server, "last_seen_at", None)
        if last_seen_at:
            seen_at = last_seen_at if last_seen_at.tzinfo else last_seen_at.replace(tzinfo=UTC)
            if (datetime.now(UTC) - seen_at).total_seconds() > 86400:
                reasons.append("provider_sync_stale")
        if metadata.get("stale_metrics"):
            reasons.append("metrics_stale")
        return reasons

    @staticmethod
    def _warnings(
        server: Any,
        *,
        node_type: str,
        provider_state: str,
        provider_guest_exists: bool,
        ssh_state: str,
        monitoring_state: str,
    ) -> list[str]:
        warnings: list[str] = []
        if node_type == ManagedNodeType.HYPERVISOR.value:
            warnings.append("hypervisor_node")
        if provider_state == "stopped":
            warnings.append("provider_guest_stopped")
        if not provider_guest_exists and RuntimeStateService._str(getattr(server, "provider", None)).lower() == "proxmox":
            warnings.append("inventory_record_retained_without_provider_guest")
        if ssh_state != "ready":
            warnings.append("ssh_runtime_actions_unavailable")
        if monitoring_state != "monitoring_ready":
            warnings.append("monitoring_not_ready")
        return warnings

    @classmethod
    def _reconciliation(
        cls,
        server: Any,
        *,
        provider: str,
        sync_state: str,
        provider_guest_exists: bool,
        metadata: dict[str, object],
    ) -> NodeRuntimeReconciliation:
        provider_link_status = "not_provider_backed"
        if provider.lower() == "proxmox":
            provider_link_status = "linked" if provider_guest_exists else "provider_guest_missing"
        drift_indicators: list[str] = []
        mismatch_explanations: list[str] = []
        if sync_state in {InventorySyncStatus.MISMATCH.value, InventorySyncStatus.ORPHANED.value, InventorySyncStatus.STALE.value}:
            drift_indicators.append(f"sync_{sync_state}")
        provider_hostname = metadata.get("provider_hostname") or metadata.get("name") or metadata.get("vm_name")
        if provider_hostname and str(provider_hostname) != cls._str(getattr(server, "hostname", None)):
            drift_indicators.append("hostname_mismatch")
            mismatch_explanations.append("Inventory hostname differs from provider guest name")
        if provider.lower() == "proxmox" and not provider_guest_exists:
            mismatch_explanations.append("Inventory record is retained without a matching provider object")
        confidence = "high" if sync_state == InventorySyncStatus.SYNCED.value and provider_guest_exists else "medium"
        if drift_indicators or sync_state in {InventorySyncStatus.UNKNOWN.value, InventorySyncStatus.ORPHANED.value}:
            confidence = "low"
        return NodeRuntimeReconciliation(
            provider_link_status=provider_link_status,
            confidence=confidence,
            drift_indicators=list(dict.fromkeys(drift_indicators)),
            mismatch_explanations=list(dict.fromkeys(mismatch_explanations)),
            provider_sync_freshness="stale" if sync_state == InventorySyncStatus.STALE.value else sync_state,
            last_reconciled_at=getattr(server, "last_sync_at", None) or getattr(server, "last_seen_at", None),
        )

    @staticmethod
    def _freshness(server: Any, *, stale_reasons: list[str]) -> NodeRuntimeFreshness:
        confidence = "low" if stale_reasons else "medium"
        if getattr(server, "last_seen_at", None) and not stale_reasons:
            confidence = "high"
        return NodeRuntimeFreshness(
            provider_refreshed_at=getattr(server, "last_seen_at", None),
            inventory_refreshed_at=getattr(server, "updated_at", None),
            runtime_refreshed_at=datetime.now(UTC),
            confidence=confidence,
        )


class _ProviderGuestInventoryShim:
    def __init__(self, vm: Any) -> None:
        self.hostname = getattr(vm, "name", "provider-guest")
        self.provider = "proxmox"
        self.vmid = str(getattr(vm, "vm_id", "")) or None
        self.external_id = self.vmid
        self.provider_node = getattr(vm, "node", None)
        self.provider_type = getattr(vm, "type", None)
        self.node_type = ManagedNodeType.LXC if self.provider_type == "lxc" else ManagedNodeType.VM
        self.managed = False
        self.management_state = ManagementState.UNMANAGED
        self.lifecycle_state = InventoryLifecycleState.DISCOVERED
        self.sync_state = InventorySyncStatus.UNMANAGED
        self.sync_status = InventorySyncStatus.UNMANAGED
        self.last_health_status = InventoryHealthStatus.UNKNOWN
        self.last_seen_at = datetime.now(UTC)
        self.provider_metadata = {"vm_status": getattr(vm, "status", "unknown")}
