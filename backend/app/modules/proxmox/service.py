from collections import Counter
from datetime import UTC, datetime
from ipaddress import ip_address
import socket
from typing import Any

import structlog

from backend.app.adapters.proxmox import ProxmoxAdapter
from backend.app.common.constants import (
    InventoryHealthStatus,
    InventoryLifecycleState,
    InventorySyncStatus,
    ManagedNodeType,
    ManagementState,
    ServerEnvironment,
    ServerSshAuthMethod,
    ServerStatus,
)
from backend.app.modules.inventory.models import Server
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.service import InventoryService
from backend.app.modules.proxmox.schemas import (
    ProxmoxClusterSummaryRead,
    ProxmoxDashboardRead,
    ProxmoxGuestSyncRead,
    ProxmoxHostSyncRead,
    ProxmoxNodeDetailRead,
    ProxmoxNodeRead,
    ProxmoxStorageRead,
    ProxmoxVmActionRead,
    ProxmoxVmRead,
)
from backend.app.modules.runtime_state.service import RuntimeStateService
from backend.app.modules.runtime_state.repository import (
    NodeRuntimeSnapshotRepository,
    RuntimeRefreshStatusRepository,
)
from backend.app.modules.runtime_state.snapshots import RuntimeSnapshotService

logger = structlog.get_logger(__name__)


class ProxmoxVmNotFoundError(Exception):
    """Raised when a requested Proxmox VM cannot be found."""


class ProxmoxVmActionNotAllowedError(Exception):
    """Raised when a VM lifecycle action is not valid for the current state."""


class ProxmoxService:
    """Application service for Proxmox visibility and controlled VM lifecycle actions."""

    def __init__(
        self,
        adapter: ProxmoxAdapter,
        *,
        server_repository: ServerRepository | None = None,
        integration_id: str | None = None,
    ) -> None:
        self.adapter = adapter
        self.server_repository = server_repository
        self.integration_id = integration_id
        self.runtime_snapshots = (
            RuntimeSnapshotService(
                NodeRuntimeSnapshotRepository(server_repository.session),
                status_repository=RuntimeRefreshStatusRepository(server_repository.session),
            )
            if server_repository is not None
            else None
        )

    async def get_nodes(self) -> list[ProxmoxNodeRead]:
        raw_nodes = await self.adapter.get_nodes()
        vms = await self.list_vms()
        storage = await self.list_storage()
        nodes = self._normalize_nodes(raw_nodes=raw_nodes, vms=vms, storage=storage)
        if self.server_repository is not None:
            nodes = await self._add_host_inventory_context(nodes)
        logger.info("proxmox_nodes_normalized", node_count=len(nodes))
        return nodes

    async def list_vms(self) -> list[ProxmoxVmRead]:
        raw_vms = await self.adapter.list_vms()
        vms = []
        for raw_vm in raw_vms:
            vm = self._normalize_vm(raw_vm)
            if vm.ip_address is None:
                detected_ip = await self._detect_guest_ip(vm)
                if detected_ip:
                    vm = vm.model_copy(update={"ip_address": detected_ip})
            vms.append(vm)
        if self.server_repository is not None:
            vms = await self._add_inventory_context(vms)
        logger.info("proxmox_vms_normalized", vm_count=len(vms))
        return vms

    async def list_storage(self, node_name: str | None = None) -> list[ProxmoxStorageRead]:
        raw_storage = await self.adapter.list_storage(node=node_name)
        storage = [self._normalize_storage(item, default_node=node_name) for item in raw_storage]
        return sorted(storage, key=lambda item: ((item.node or ""), item.storage))

    async def get_vm_status(self, *, node: str, vm_id: int, vm_type: str) -> ProxmoxVmRead:
        raw_status = await self.adapter.get_vm_status(node=node, vm_id=vm_id, vm_type=vm_type)
        return self._normalize_vm({**raw_status, "node": node, "vmid": vm_id, "type": vm_type})

    async def get_cluster_summary(self) -> ProxmoxClusterSummaryRead:
        raw_nodes = await self.adapter.get_nodes()
        vms = await self.list_vms()
        storage = await self.list_storage()
        nodes = self._normalize_nodes(raw_nodes=raw_nodes, vms=vms, storage=storage)
        if self.server_repository is not None:
            nodes = await self._add_host_inventory_context(nodes)
        return self._build_summary(nodes=nodes, vms=vms)

    async def get_dashboard(self) -> ProxmoxDashboardRead:
        raw_nodes = await self.adapter.get_nodes()
        vms = await self.list_vms()
        storage = await self.list_storage()
        nodes = self._normalize_nodes(raw_nodes=raw_nodes, vms=vms, storage=storage)
        if self.server_repository is not None:
            nodes = await self._add_host_inventory_context(nodes)
        return ProxmoxDashboardRead(
            summary=self._build_summary(nodes=nodes, vms=vms),
            nodes=nodes,
            vms=vms,
        )

    async def get_node_detail(self, node_name: str) -> ProxmoxNodeDetailRead:
        raw_nodes = await self.adapter.get_nodes()
        vms = await self.list_vms()
        storage = await self.list_storage(node_name)
        nodes = self._normalize_nodes(raw_nodes=raw_nodes, vms=vms, storage=storage)
        if self.server_repository is not None:
            nodes = await self._add_host_inventory_context(nodes)
        node = next((candidate for candidate in nodes if candidate.name == node_name), None)
        if node is None:
            raise ProxmoxVmNotFoundError("Node not found")
        return ProxmoxNodeDetailRead(
            node=node,
            vms=[vm for vm in vms if vm.node == node_name],
            storage_usage=[item.model_dump() for item in storage],
            detected_services=self._host_services(node),
        )

    async def sync_hosts(self) -> ProxmoxHostSyncRead:
        if self.server_repository is None:
            raise ProxmoxVmActionNotAllowedError("Server repository is required for host synchronization")

        raw_nodes = await self.adapter.get_nodes()
        vms = await self.list_vms()
        storage = await self.list_storage()
        nodes = self._normalize_nodes(raw_nodes=raw_nodes, vms=vms, storage=storage)

        imported = 0
        updated = 0
        skipped: list[str] = []
        synced_hosts: list[ProxmoxNodeRead] = []
        now = datetime.now(UTC)

        for node in nodes:
            management_ip = node.management_ip or self._resolve_node_ip(node.name)
            if not management_ip:
                skipped.append(f"{node.name}: management IP could not be discovered")
                continue

            external_id = self._host_external_id(node.name)
            existing = await self.server_repository.get_by_provider_external_id("proxmox", external_id)
            if existing is None:
                existing = await self.server_repository.get_by_provider_external_id("proxmox", node.name)
            if existing is None:
                existing = await self.server_repository.get_by_hostname(node.name)

            metadata = self._host_metadata(node)
            capabilities = self._host_capabilities(node)
            if existing is None:
                server = Server(
                    hostname=node.name,
                    ip_address=management_ip,
                    operating_system="Proxmox VE",
                    vmid=None,
                    node_type=ManagedNodeType.HYPERVISOR,
                    environment=ServerEnvironment.LAB,
                    tags=["source:proxmox", "hypervisor", "managed"],
                    ssh_port=22,
                    ssh_username="root",
                    ssh_auth_method=ServerSshAuthMethod.KEY,
                    status=ServerStatus.ONLINE if node.status == "online" else ServerStatus.OFFLINE,
                    provider="proxmox",
                    external_id=external_id,
                    source="imported",
                    managed=True,
                    management_state=ManagementState.MANAGED,
                    lifecycle_state=InventoryLifecycleState.MANAGED,
                    sync_status=InventorySyncStatus.SYNCED,
                    sync_state=InventorySyncStatus.SYNCED,
                    provider_node=node.name,
                    provider_type="node",
                    provider_metadata=metadata,
                    capabilities=capabilities,
                    last_seen_at=now,
                    last_health_status=InventoryHealthStatus.ONLINE if node.status == "online" else InventoryHealthStatus.UNKNOWN,
                )
                await self.server_repository.create(server)
                imported += 1
            else:
                existing.ip_address = management_ip
                existing.operating_system = existing.operating_system or "Proxmox VE"
                existing.node_type = ManagedNodeType.HYPERVISOR
                existing.status = ServerStatus.ONLINE if node.status == "online" else ServerStatus.OFFLINE
                existing.provider = "proxmox"
                existing.external_id = external_id
                existing.provider_node = node.name
                existing.provider_type = "node"
                existing.provider_metadata = {**existing.provider_metadata, **metadata}
                existing.capabilities = sorted(set([*existing.capabilities, *capabilities]))
                existing.managed = True
                existing.management_state = ManagementState.MANAGED
                existing.lifecycle_state = InventoryLifecycleState.MANAGED
                existing.sync_status = InventorySyncStatus.SYNCED
                existing.sync_state = InventorySyncStatus.SYNCED
                existing.last_health_status = (
                    InventoryHealthStatus.ONLINE if node.status == "online" else InventoryHealthStatus.UNKNOWN
                )
                existing.last_seen_at = now
                updated += 1

            synced_hosts.append(node.model_copy(update={"management_ip": management_ip, "inventory_sync_status": "synced"}))

        await self.server_repository.session.commit()
        enriched = await self._add_host_inventory_context(synced_hosts)
        return ProxmoxHostSyncRead(
            discovered_count=len(nodes),
            imported_count=imported,
            updated_count=updated,
            skipped_count=len(skipped),
            hosts=enriched,
            skipped=skipped,
        )

    async def sync_guests(self) -> ProxmoxGuestSyncRead:
        if self.server_repository is None:
            raise ProxmoxVmActionNotAllowedError("Server repository is required for guest synchronization")

        guests = await self.list_vms()
        imported = 0
        updated = 0
        skipped: list[str] = []
        now = datetime.now(UTC)

        for guest in guests:
            if guest.template:
                continue
            ip_value = guest.ip_address or self._placeholder_ip_for_guest(guest.vm_id)
            existing = await self.server_repository.get_by_provider_external_id("proxmox", str(guest.vm_id))
            if existing is None:
                existing = await self.server_repository.get_by_hostname(guest.name)
            if existing is None and guest.ip_address:
                existing = await self.server_repository.get_by_ip_address(guest.ip_address)

            metadata = self._guest_metadata(guest)
            if existing is None:
                server = Server(
                    hostname=guest.name,
                    ip_address=ip_value,
                    operating_system="Linux container" if guest.type == "lxc" else "Linux guest",
                    vmid=str(guest.vm_id),
                    node_type=ManagedNodeType.LXC if guest.type == "lxc" else ManagedNodeType.VM,
                    environment=ServerEnvironment.LAB,
                    tags=["source:proxmox", guest.type, "discovered"],
                    ssh_port=22,
                    ssh_username="root" if guest.type == "lxc" else "ubuntu",
                    ssh_auth_method=ServerSshAuthMethod.KEY,
                    status=self._server_status_from_guest(guest),
                    provider="proxmox",
                    external_id=str(guest.vm_id),
                    source="imported",
                    managed=False,
                    management_state=ManagementState.UNMANAGED,
                    lifecycle_state=InventoryLifecycleState.UNMANAGED,
                    sync_status=InventorySyncStatus.UNMANAGED,
                    sync_state=InventorySyncStatus.UNMANAGED,
                    provider_node=guest.node,
                    provider_type=guest.type,
                    provider_metadata=metadata,
                    capabilities=self._guest_capabilities(guest),
                    last_seen_at=now,
                    last_health_status=self._health_status_from_readiness(guest.operational_readiness),
                )
                await self.server_repository.create(server)
                imported += 1
            else:
                if existing.lifecycle_state in {
                    InventoryLifecycleState.ARCHIVED,
                    InventoryLifecycleState.DECOMMISSIONED,
                    InventoryLifecycleState.DELETED,
                }:
                    skipped.append(f"{guest.name}: inactive inventory record retained")
                    continue
                existing.hostname = existing.hostname or guest.name
                if guest.ip_address and existing.ip_address in {"", "0.0.0.0", metadata.get("previous_detected_ip")}:
                    existing.ip_address = guest.ip_address
                existing.vmid = str(guest.vm_id)
                existing.node_type = ManagedNodeType.LXC if guest.type == "lxc" else ManagedNodeType.VM
                existing.status = self._server_status_from_guest(guest)
                existing.provider = "proxmox"
                existing.external_id = str(guest.vm_id)
                existing.provider_node = guest.node
                existing.provider_type = guest.type
                existing.provider_metadata = {**existing.provider_metadata, **metadata}
                existing.capabilities = sorted(set([*existing.capabilities, *self._guest_capabilities(guest)]))
                existing.last_seen_at = now
                existing.last_health_status = self._health_status_from_readiness(guest.operational_readiness)
                if existing.managed:
                    existing.sync_status = InventorySyncStatus.SYNCED
                    existing.sync_state = InventorySyncStatus.SYNCED
                updated += 1

        await self.server_repository.session.commit()
        enriched = await self._add_inventory_context(guests)
        return ProxmoxGuestSyncRead(
            discovered_count=len([guest for guest in guests if not guest.template]),
            imported_count=imported,
            updated_count=updated,
            skipped_count=len(skipped),
            guests=enriched,
            skipped=skipped,
        )

    async def start_vm(self, vm_id: int) -> ProxmoxVmActionRead:
        return await self._run_vm_action(vm_id=vm_id, action="start")

    async def stop_vm(self, vm_id: int) -> ProxmoxVmActionRead:
        return await self._run_vm_action(vm_id=vm_id, action="stop")

    async def reboot_vm(self, vm_id: int) -> ProxmoxVmActionRead:
        return await self._run_vm_action(vm_id=vm_id, action="reboot")

    async def shutdown_vm(self, vm_id: int) -> ProxmoxVmActionRead:
        return await self._run_vm_action(vm_id=vm_id, action="shutdown")

    async def _run_vm_action(self, *, vm_id: int, action: str) -> ProxmoxVmActionRead:
        vm = await self._find_vm(vm_id)
        self._validate_action(vm=vm, action=action)

        logger.info(
            "proxmox_vm_action_requested",
            vm_id=vm.vm_id,
            node=vm.node,
            vm_type=vm.type,
            action=action,
            current_status=vm.status,
        )

        try:
            raw_response = await self._dispatch_action(vm=vm, action=action)
        except Exception:
            logger.warning(
                "proxmox_vm_action_failed",
                vm_id=vm.vm_id,
                node=vm.node,
                vm_type=vm.type,
                action=action,
                exc_info=True,
            )
            raise

        task_id = _optional_str(raw_response.get("task_id"))
        logger.info(
            "proxmox_vm_action_succeeded",
            vm_id=vm.vm_id,
            node=vm.node,
            vm_type=vm.type,
            action=action,
            task_id=task_id,
        )

        return ProxmoxVmActionRead(
            vm_id=vm.vm_id,
            name=vm.name,
            node=vm.node,
            type=vm.type,
            action=action,
            status="accepted",
            task_id=task_id,
            message=f"VM {action} action accepted by Proxmox.",
        )

    async def _find_vm(self, vm_id: int) -> ProxmoxVmRead:
        vms = await self.list_vms()
        for vm in vms:
            if vm.vm_id == vm_id:
                return vm
        logger.warning("proxmox_vm_action_failed", vm_id=vm_id, reason="not_found")
        raise ProxmoxVmNotFoundError("VM not found")

    @staticmethod
    def _validate_action(*, vm: ProxmoxVmRead, action: str) -> None:
        if action == "start" and vm.status == "running":
            raise ProxmoxVmActionNotAllowedError("VM is already running")

        if action in {"stop", "reboot", "shutdown"} and vm.status != "running":
            raise ProxmoxVmActionNotAllowedError(
                f"VM must be running before {action} can be requested"
            )
    async def _dispatch_action(self, *, vm: ProxmoxVmRead, action: str) -> dict[str, Any]:
        if action == "start":
            return await self.adapter.start_vm(node=vm.node, vm_id=vm.vm_id, vm_type=vm.type)
        if action == "stop":
            return await self.adapter.stop_vm(node=vm.node, vm_id=vm.vm_id, vm_type=vm.type)
        if action == "reboot":
            return await self.adapter.reboot_vm(node=vm.node, vm_id=vm.vm_id, vm_type=vm.type)
        if action == "shutdown":
            return await self.adapter.shutdown_vm(node=vm.node, vm_id=vm.vm_id, vm_type=vm.type)
        raise ProxmoxVmActionNotAllowedError("Unsupported VM action")

    @classmethod
    def _normalize_nodes(
        cls,
        *,
        raw_nodes: list[dict[str, Any]],
        vms: list[ProxmoxVmRead],
        storage: list[ProxmoxStorageRead] | None = None,
    ) -> list[ProxmoxNodeRead]:
        vm_counts = Counter(vm.node for vm in vms if vm.type == "qemu")
        running_vm_counts = Counter(vm.node for vm in vms if vm.type == "qemu" and vm.status == "running")
        lxc_counts = Counter(vm.node for vm in vms if vm.type == "lxc")
        running_lxc_counts = Counter(vm.node for vm in vms if vm.type == "lxc" and vm.status == "running")
        storage_by_node: dict[str, tuple[int, int]] = {}
        for item in storage or []:
            if not item.node:
                continue
            used, total = storage_by_node.get(item.node, (0, 0))
            storage_by_node[item.node] = (used + (item.used_bytes or 0), total + (item.total_bytes or 0))
        return [
            cls._normalize_node(
                node,
                vm_count=vm_counts.get(str(node.get("node")), 0),
                running_vm_count=running_vm_counts.get(str(node.get("node")), 0),
                lxc_count=lxc_counts.get(str(node.get("node")), 0),
                running_lxc_count=running_lxc_counts.get(str(node.get("node")), 0),
                storage=storage_by_node.get(str(node.get("node")), (0, 0)),
            )
            for node in raw_nodes
        ]

    @staticmethod
    def _normalize_node(
        raw_node: dict[str, Any],
        *,
        vm_count: int,
        running_vm_count: int,
        lxc_count: int,
        running_lxc_count: int,
        storage: tuple[int, int],
    ) -> ProxmoxNodeRead:
        return ProxmoxNodeRead(
            name=str(raw_node.get("node", "unknown")),
            status=str(raw_node.get("status", "unknown")),
            management_ip=_optional_str(raw_node.get("ip") or raw_node.get("ip_address") or raw_node.get("management_ip")),
            cpu_usage=_optional_float(raw_node.get("cpu")),
            memory_used=_optional_int(raw_node.get("mem")),
            memory_total=_optional_int(raw_node.get("maxmem")),
            storage_used=storage[0] or None,
            storage_total=storage[1] or None,
            uptime_seconds=_optional_int(raw_node.get("uptime")),
            vm_count=vm_count,
            running_vm_count=running_vm_count,
            lxc_count=lxc_count,
            running_lxc_count=running_lxc_count,
            capabilities=["proxmox_node", "monitoring", "ssh", "shell", "filesystem"],
        )

    @staticmethod
    def _normalize_vm(raw_vm: dict[str, Any]) -> ProxmoxVmRead:
        vm_id = _optional_int(raw_vm.get("vmid")) or 0
        vm_type = str(raw_vm.get("type", "unknown"))
        ip_addresses = _guest_ips_from_raw(raw_vm)
        primary_ip = _optional_str(
            raw_vm.get("ip")
            or raw_vm.get("ip_address")
            or raw_vm.get("guest_ip")
            or raw_vm.get("agent_ip")
        ) or (ip_addresses[0] if ip_addresses else None)
        status = str(raw_vm.get("status", "unknown"))
        readiness, readiness_notes = _guest_readiness(
            status=status,
            ip_address=primary_ip,
            vm_type=vm_type,
        )
        return ProxmoxVmRead(
            vm_id=vm_id,
            name=str(raw_vm.get("name") or raw_vm.get("id") or f"vm-{vm_id}"),
            node=str(raw_vm.get("node", "unknown")),
            type=vm_type,
            status=status,
            cpu_usage=_optional_float(raw_vm.get("cpu")),
            memory_used=_optional_int(raw_vm.get("mem")),
            memory_total=_optional_int(raw_vm.get("maxmem")),
            disk_used=_optional_int(raw_vm.get("disk")),
            disk_total=_optional_int(raw_vm.get("maxdisk")),
            uptime_seconds=_optional_int(raw_vm.get("uptime")),
            ip_address=primary_ip,
            ip_addresses=ip_addresses,
            template=bool(raw_vm.get("template")),
            template_ref=_optional_str(raw_vm.get("template_ref") or raw_vm.get("ostemplate")),
            source_template=_optional_str(raw_vm.get("template") if isinstance(raw_vm.get("template"), str) else raw_vm.get("ostemplate")),
            operational_readiness=readiness,
            readiness_notes=readiness_notes,
        )

    @staticmethod
    def _normalize_storage(raw_storage: dict[str, Any], *, default_node: str | None = None) -> ProxmoxStorageRead:
        content = raw_storage.get("content") or ""
        if isinstance(content, str):
            content_items = [item.strip() for item in content.split(",") if item.strip()]
        elif isinstance(content, list):
            content_items = [str(item) for item in content]
        else:
            content_items = []

        return ProxmoxStorageRead(
            storage=str(raw_storage.get("storage") or raw_storage.get("id") or "unknown"),
            node=_optional_str(raw_storage.get("node")) or default_node,
            type=_optional_str(raw_storage.get("type")),
            content=content_items,
            active=_optional_bool(raw_storage.get("active")),
            enabled=_optional_bool(raw_storage.get("enabled")),
            shared=_optional_bool(raw_storage.get("shared")),
            used_bytes=_optional_int(raw_storage.get("used")),
            total_bytes=_optional_int(raw_storage.get("total") or raw_storage.get("maxdisk")),
            available_bytes=_optional_int(raw_storage.get("avail")),
        )

    async def _add_inventory_context(self, vms: list[ProxmoxVmRead]) -> list[ProxmoxVmRead]:
        if self.server_repository is None:
            return vms

        inventory = await self.server_repository.list_by_provider("proxmox")
        enriched: list[ProxmoxVmRead] = []
        for vm in vms:
            match, sync_status, notes = InventoryService.match_discovered_vm(vm, inventory)
            runtime_state = RuntimeStateService.from_provider_guest(vm, match)
            if match is not None and self.runtime_snapshots is not None:
                snapshot = await self.runtime_snapshots.refresh_provider_snapshot(
                    match,
                    provider_state=vm.status,
                    provider_reachable=True,
                    provider_guest_exists=not vm.template,
                    commit=False,
                )
                runtime_state = self.runtime_snapshots.to_runtime_state(snapshot)
            enriched.append(
                vm.model_copy(
                    update={
                        "inventory_server_id": str(match.id) if match else None,
                        "inventory_hostname": match.hostname if match else None,
                        "inventory_lifecycle_state": match.lifecycle_state.value if match else None,
                        "inventory_sync_status": sync_status.value,
                        "inventory_notes": notes,
                        "runtime_state": runtime_state,
                    }
                )
            )
        if self.runtime_snapshots is not None:
            await self.runtime_snapshots.record_refresh_status(
                "provider",
                "success",
                metadata_json={"vm_count": len(vms)},
                commit=False,
            )
            await self.server_repository.session.commit()
        return enriched

    async def _add_host_inventory_context(self, nodes: list[ProxmoxNodeRead]) -> list[ProxmoxNodeRead]:
        if self.server_repository is None:
            return nodes
        inventory = await self.server_repository.list_by_provider("proxmox")
        enriched: list[ProxmoxNodeRead] = []
        for node in nodes:
            match = next(
                (
                    server
                    for server in inventory
                    if server.node_type == ManagedNodeType.HYPERVISOR
                    and (
                        server.external_id == self._host_external_id(node.name)
                        or server.external_id == node.name
                        or server.hostname == node.name
                    )
                ),
                None,
            )
            runtime_state = None
            if match and self.runtime_snapshots is not None:
                snapshot = await self.runtime_snapshots.refresh_provider_snapshot(
                    match,
                    provider_state=node.status,
                    provider_reachable=node.status == "online",
                    provider_guest_exists=True,
                    commit=False,
                )
                runtime_state = self.runtime_snapshots.to_runtime_state(snapshot)
            elif match:
                runtime_state = RuntimeStateService.from_inventory_node(
                    match,
                    provider_state=node.status,
                    provider_reachable=node.status == "online",
                    provider_guest_exists=True,
                )
            enriched.append(
                node.model_copy(
                    update={
                        "management_ip": node.management_ip or (match.ip_address if match else None),
                        "inventory_server_id": str(match.id) if match else None,
                        "inventory_hostname": match.hostname if match else None,
                        "inventory_lifecycle_state": match.lifecycle_state.value if match else None,
                        "inventory_sync_status": self._host_sync_status(match),
                        "runtime_state": runtime_state,
                    }
                )
            )
        if self.runtime_snapshots is not None:
            await self.runtime_snapshots.record_refresh_status(
                "provider",
                "success",
                metadata_json={"node_count": len(nodes)},
                commit=False,
            )
            await self.server_repository.session.commit()
        return enriched

    @staticmethod
    def _host_sync_status(match: Server | None) -> str:
        if match is None:
            return InventorySyncStatus.UNMANAGED.value
        if match.lifecycle_state in {InventoryLifecycleState.ARCHIVED, InventoryLifecycleState.DECOMMISSIONED}:
            return InventorySyncStatus.ARCHIVED.value
        return InventorySyncStatus.SYNCED.value if match.managed else InventorySyncStatus.UNMANAGED.value

    @staticmethod
    def _resolve_node_ip(node_name: str) -> str | None:
        try:
            return str(ip_address(node_name))
        except ValueError:
            pass
        try:
            return socket.gethostbyname(node_name)
        except OSError:
            return None

    @staticmethod
    def _host_capabilities(node: ProxmoxNodeRead) -> list[str]:
        capabilities = ["proxmox_node", "monitoring", "ssh", "shell", "filesystem"]
        if node.storage_total:
            capabilities.append("storage")
        if node.vm_count:
            capabilities.append("vm_host")
        if node.lxc_count:
            capabilities.append("lxc_host")
        return sorted(set(capabilities))

    def _host_external_id(self, node_name: str) -> str:
        return f"{self.integration_id}:{node_name}" if self.integration_id else node_name

    def _host_metadata(self, node: ProxmoxNodeRead) -> dict[str, object]:
        return {
            "integration_id": self.integration_id,
            "node_status": node.status,
            "uptime_seconds": node.uptime_seconds,
            "cpu_usage": node.cpu_usage,
            "memory_used": node.memory_used,
            "memory_total": node.memory_total,
            "storage_used": node.storage_used,
            "storage_total": node.storage_total,
            "vm_count": node.vm_count,
            "running_vm_count": node.running_vm_count,
            "lxc_count": node.lxc_count,
            "running_lxc_count": node.running_lxc_count,
            "detected_services": self._host_services(node),
        }

    @staticmethod
    def _host_services(node: ProxmoxNodeRead) -> list[str]:
        services = ["proxmox-api", "ssh"]
        if node.storage_total:
            services.append("storage")
        return services

    async def _detect_guest_ip(self, vm: ProxmoxVmRead) -> str | None:
        try:
            interfaces = await self.adapter.get_vm_network_interfaces(
                node=vm.node,
                vm_id=vm.vm_id,
                vm_type=vm.type,
            )
        except Exception:
            return None
        return _first_guest_ip(interfaces)

    @staticmethod
    def _server_status_from_guest(guest: ProxmoxVmRead) -> ServerStatus:
        return ServerStatus.ONLINE if guest.status == "running" else ServerStatus.OFFLINE

    @staticmethod
    def _guest_capabilities(guest: ProxmoxVmRead) -> list[str]:
        capabilities = ["monitoring", "provisioning"]
        if guest.ip_address:
            capabilities.extend(["ssh", "shell", "filesystem", "identity"])
        if guest.type == "lxc":
            capabilities.append("lxc")
        else:
            capabilities.append("vm")
        return sorted(set(capabilities))

    @staticmethod
    def _guest_metadata(guest: ProxmoxVmRead) -> dict[str, object]:
        return {
            "vm_name": guest.name,
            "vm_status": guest.status,
            "detected_ip_address": guest.ip_address,
            "detected_ip_addresses": guest.ip_addresses,
            "operational_readiness": guest.operational_readiness,
            "readiness_notes": guest.readiness_notes,
            "template_ref": guest.template_ref,
            "source_template": guest.source_template,
            "cpu_usage": guest.cpu_usage,
            "memory_used": guest.memory_used,
            "memory_total": guest.memory_total,
            "disk_used": guest.disk_used,
            "disk_total": guest.disk_total,
            "uptime_seconds": guest.uptime_seconds,
        }

    @staticmethod
    def _health_status_from_readiness(readiness: str) -> InventoryHealthStatus:
        if readiness in {"booted", "partially_managed"}:
            return InventoryHealthStatus.ONLINE
        if readiness in {"network_missing", "ip_missing", "dns_failed", "ssh_unreachable", "degraded"}:
            return InventoryHealthStatus.SYNC_ERROR
        return InventoryHealthStatus.UNKNOWN

    @staticmethod
    def _placeholder_ip_for_guest(vm_id: int) -> str:
        return f"0.{(vm_id >> 16) & 255}.{(vm_id >> 8) & 255}.{vm_id & 255}"

    @staticmethod
    def _build_summary(
        *,
        nodes: list[ProxmoxNodeRead],
        vms: list[ProxmoxVmRead],
    ) -> ProxmoxClusterSummaryRead:
        memory_used = sum(node.memory_used or 0 for node in nodes)
        memory_total = sum(node.memory_total or 0 for node in nodes)
        cpu_values = [node.cpu_usage for node in nodes if node.cpu_usage is not None]

        return ProxmoxClusterSummaryRead(
            node_count=len(nodes),
            online_node_count=sum(1 for node in nodes if node.status == "online"),
            vm_count=len(vms),
            running_vm_count=sum(1 for vm in vms if vm.status == "running"),
            stopped_vm_count=sum(1 for vm in vms if vm.status == "stopped"),
            cpu_usage=sum(cpu_values) / len(cpu_values) if cpu_values else None,
            memory_used=memory_used or None,
            memory_total=memory_total or None,
        )


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    try:
        return bool(int(value))
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _first_guest_ip(interfaces: list[dict[str, Any]]) -> str | None:
    for interface in interfaces:
        addresses = interface.get("ip-addresses") or interface.get("ip_addresses") or []
        if not isinstance(addresses, list):
            continue
        for address in addresses:
            if not isinstance(address, dict):
                continue
            ip_address = _optional_str(address.get("ip-address") or address.get("ip_address"))
            ip_type = _optional_str(address.get("ip-address-type") or address.get("ip_address_type"))
            if not ip_address or ip_type == "ipv6" or ip_address.startswith("127."):
                continue
            return ip_address
    return None


def _guest_ips_from_raw(raw_vm: dict[str, Any]) -> list[str]:
    raw_values = raw_vm.get("ips") or raw_vm.get("ip_addresses") or raw_vm.get("networks") or []
    if isinstance(raw_values, str):
        candidates = [item.strip() for item in raw_values.replace(";", ",").split(",")]
    elif isinstance(raw_values, list):
        candidates = [str(item.get("ip") if isinstance(item, dict) else item).strip() for item in raw_values]
    else:
        candidates = []
    direct = _optional_str(
        raw_vm.get("ip")
        or raw_vm.get("ip_address")
        or raw_vm.get("guest_ip")
        or raw_vm.get("agent_ip")
    )
    if direct:
        candidates.insert(0, direct)

    normalized: list[str] = []
    for candidate in candidates:
        value = candidate.split("/", 1)[0]
        if not value or value.startswith("127.") or ":" in value:
            continue
        if value not in normalized:
            normalized.append(value)
    return normalized


def _guest_readiness(*, status: str, ip_address: str | None, vm_type: str) -> tuple[str, list[str]]:
    if status != "running":
        return "discovered", ["Guest exists in Proxmox but is not running."]
    if not ip_address:
        return "ip_missing", ["Guest is running, but no IPv4 address was discovered."]
    notes = [
        "Guest is running and has an IP address.",
        "SSH readiness is validated separately by managed node health, jobs, and remote access.",
    ]
    if vm_type == "lxc":
        notes.append("LXC shell access depends on SSH being installed, reachable, and credentialed inside the container.")
    return "booted", notes
