from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from backend.app.common.constants import (
    InventoryHealthStatus,
    InventoryLifecycleState,
    InventorySyncStatus,
    ManagedNodeType,
    ManagementState,
    ServerStatus,
)
from backend.app.modules.runtime_state.service import RuntimeStateService


def test_provider_lifecycle_does_not_depend_on_ssh_reachability() -> None:
    state = RuntimeStateService.from_inventory_node(
        _server(
            status=ServerStatus.OFFLINE,
            last_health_status=InventoryHealthStatus.UNREACHABLE,
            provider_metadata={"vm_status": "stopped"},
        )
    )

    assert state.provider_state == "stopped"
    assert state.ssh_state == "unreachable"
    assert state.eligibility.can_start is True
    assert state.eligibility.can_stop is False
    assert state.eligibility.can_reboot is False
    assert state.eligibility.can_run_jobs is False
    assert state.eligibility.can_open_shell is False


def test_running_provider_guest_allows_lifecycle_when_ssh_is_down() -> None:
    state = RuntimeStateService.from_inventory_node(
        _server(
            status=ServerStatus.ONLINE,
            last_health_status=InventoryHealthStatus.UNREACHABLE,
            provider_metadata={"vm_status": "running"},
        )
    )

    assert state.eligibility.can_start is False
    assert state.eligibility.can_stop is True
    assert state.eligibility.can_reboot is True
    assert state.eligibility.can_deploy is False
    assert "ssh_unreachable" in state.degraded_reasons


def test_orphaned_inventory_survives_as_degraded_without_provider_actions() -> None:
    state = RuntimeStateService.from_inventory_node(
        _server(
            sync_state=InventorySyncStatus.ORPHANED,
            sync_status=InventorySyncStatus.ORPHANED,
            last_health_status=InventoryHealthStatus.ONLINE,
        )
    )

    assert state.provider_guest_exists is False
    assert state.eligibility.can_start is False
    assert state.eligibility.can_stop is False
    assert state.eligibility.can_run_jobs is True
    assert "provider_guest_missing" in state.degraded_reasons
    assert "sync_orphaned" in state.stale_reasons


def test_monitoring_state_is_independent_from_lifecycle_and_jobs() -> None:
    state = RuntimeStateService.from_inventory_node(
        _server(
            last_health_status=InventoryHealthStatus.ONLINE,
            provider_metadata={
                "vm_status": "running",
                "monitoring_state": "monitoring_missing",
            },
        )
    )

    assert state.monitoring_state == "monitoring_missing"
    assert state.eligibility.can_stop is True
    assert state.eligibility.can_run_jobs is True
    assert state.eligibility.can_monitor is True
    assert "monitoring_missing" in state.degraded_reasons


def test_inactive_inventory_blocks_runtime_and_lifecycle_actions() -> None:
    state = RuntimeStateService.from_inventory_node(
        _server(
            lifecycle_state=InventoryLifecycleState.DECOMMISSIONED,
            managed=False,
            management_state=ManagementState.RETIRED,
            last_health_status=InventoryHealthStatus.ONLINE,
            provider_metadata={"vm_status": "running"},
        )
    )

    assert state.orchestration_state == "inactive"
    assert state.eligibility.can_stop is False
    assert state.eligibility.can_run_jobs is False
    assert "inventory_decommissioned" in state.degraded_reasons


def _server(**overrides):
    data = {
        "provider": "proxmox",
        "vmid": "101",
        "external_id": "101",
        "provider_node": "pve-01",
        "provider_type": "qemu",
        "node_type": ManagedNodeType.VM,
        "managed": True,
        "management_state": ManagementState.MANAGED,
        "lifecycle_state": InventoryLifecycleState.MANAGED,
        "sync_state": InventorySyncStatus.SYNCED,
        "sync_status": InventorySyncStatus.SYNCED,
        "status": ServerStatus.ONLINE,
        "last_health_status": InventoryHealthStatus.UNKNOWN,
        "last_seen_at": datetime.now(UTC) - timedelta(minutes=5),
        "provider_metadata": {},
    }
    data.update(overrides)
    return SimpleNamespace(**data)
