"""
Reconciliation service for matching discovered infrastructure with inventory records.

Implements the core matching strategies for determining synchronization state.
"""

import structlog
from datetime import UTC, datetime

from backend.app.common.constants import (
    InventoryLifecycleState,
    InventorySyncStatus,
    ServerStatus,
)
from backend.app.modules.inventory.models import Server
from backend.app.modules.proxmox.schemas import ProxmoxVmRead

logger = structlog.get_logger(__name__)


class InventoryReconciliationService:
    """Reconciles discovered infrastructure with inventory records.

    Matching strategy (priority order):
    1. Provider + External ID (most specific, Proxmox VMID)
    2. Hostname (infrastructure name matches inventory hostname)
    3. IP Address (IP match when others fail)

    Sync states indicate the relationship between discovered VM and inventory record.
    """

    @staticmethod
    def reconcile_proxmox_vm(
        vm: ProxmoxVmRead,
        inventory: list[Server],
    ) -> tuple[Server | None, InventorySyncStatus, list[str]]:
        """
        Reconcile a discovered Proxmox VM with inventory records.

        Args:
            vm: Discovered Proxmox VM from provider
            inventory: Inventory records to match against (pre-filtered to provider)

        Returns:
            Tuple of (matched_server, sync_status, notes)
            - matched_server: Inventory record matching the VM, or None if not found
            - sync_status: Reconciliation state (see InventorySyncStatus)
            - notes: Human-readable reconciliation details
        """
        notes: list[str] = []

        # Strategy 1: Match by provider + external_id (primary key match)
        match = InventoryReconciliationService._match_by_provider_id(
            vm, inventory, notes
        )

        # Strategy 2: Match by hostname (fallback 1)
        if not match:
            match = InventoryReconciliationService._match_by_hostname(vm, inventory, notes)

        # Strategy 3: Match by IP address (fallback 2)
        if not match and vm.ip_address:
            match = InventoryReconciliationService._match_by_ip_address(
                vm, inventory, notes
            )

        # No match found: VM is discovered but unmanaged
        if not match:
            logger.info(
                "inventory_reconciliation_unmanaged",
                vm_id=vm.vm_id,
                vm_name=vm.name,
                reason="no_inventory_match",
            )
            return None, InventorySyncStatus.UNMANAGED, [
                "Discovered in Proxmox but not in inventory.",
            ]

        # Match found: determine sync status
        status = InventoryReconciliationService._determine_sync_status(match, vm, notes)

        logger.info(
            "inventory_reconciliation_matched",
            vm_id=vm.vm_id,
            vm_name=vm.name,
            inventory_id=str(match.id),
            inventory_hostname=match.hostname,
            sync_status=status.value,
        )

        return match, status, notes

    @staticmethod
    def _match_by_provider_id(
        vm: ProxmoxVmRead,
        inventory: list[Server],
        notes: list[str],
    ) -> Server | None:
        """Match by provider + external_id (Proxmox VMID).

        This is the most specific and reliable match strategy.
        """
        for server in inventory:
            if server.provider == "proxmox" and (
                server.external_id == str(vm.vm_id) or server.vmid == str(vm.vm_id)
            ):
                if server.external_id and server.external_id != str(vm.vm_id):
                    notes.append(
                        f"Matched by VMID (external_id={server.external_id}, "
                        f"vmid={server.vmid})"
                    )
                return server
        return None

    @staticmethod
    def _match_by_hostname(
        vm: ProxmoxVmRead,
        inventory: list[Server],
        notes: list[str],
    ) -> Server | None:
        """Match by hostname (Proxmox name == Inventory hostname).

        Fallback strategy when provider ID match fails.
        Indicates the VM was likely imported previously without full linking.
        """
        for server in inventory:
            if server.hostname == vm.name:
                notes.append(
                    "Matched by hostname; provider VMID not yet linked to inventory."
                )
                return server
        return None

    @staticmethod
    def _match_by_ip_address(
        vm: ProxmoxVmRead,
        inventory: list[Server],
        notes: list[str],
    ) -> Server | None:
        """Match by IP address.

        Last resort fallback strategy. Indicates weak match confidence.
        """
        for server in inventory:
            if server.ip_address == vm.ip_address:
                notes.append(
                    "Matched by IP address; hostname and VMID do not match. "
                    "Verify this is the correct server."
                )
                return server
        return None

    @staticmethod
    def _determine_sync_status(
        server: Server,
        vm: ProxmoxVmRead,
        notes: list[str],
    ) -> InventorySyncStatus:
        """Determine synchronization status between inventory and provider.

        Checks for lifecycle state and metadata agreement.
        """
        # Archived inventory entries are never in sync with active VMs
        if server.lifecycle_state == InventoryLifecycleState.ARCHIVED:
            notes.append("Inventory record is archived; VM is still active.")
            return InventorySyncStatus.ARCHIVED

        # Hostname mismatch indicates metadata divergence
        if server.hostname != vm.name:
            notes.append(
                f"Inventory hostname ({server.hostname}) differs from "
                f"Proxmox VM name ({vm.name})."
            )
            return InventorySyncStatus.MISMATCH

        # Managed, fully-linked inventory entries are synced
        if server.managed:
            return InventorySyncStatus.SYNCED

        # Unmanaged inventory entries may match but are not actively managed
        return InventorySyncStatus.UNMANAGED

    @staticmethod
    def update_server_from_vm(
        server: Server,
        vm: ProxmoxVmRead,
    ) -> None:
        """Update inventory record with discovered VM metadata.

        Synchronizes CMDB with provider state.
        """
        # Link provider metadata
        server.external_id = str(vm.vm_id)
        server.vmid = str(vm.vm_id)
        server.provider_node = vm.node
        server.provider_type = vm.type

        # Update operational state
        server.status = (
            ServerStatus.ONLINE if vm.status == "running" else ServerStatus.OFFLINE
        )

        # Store provider metadata
        server.provider_metadata = {
            **server.provider_metadata,
            "vm_name": vm.name,
            "vm_status": vm.status,
            "last_reconciled": datetime.now(UTC).isoformat(),
        }
