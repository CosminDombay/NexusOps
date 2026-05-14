from collections import Counter
from typing import Any

import structlog

from backend.app.adapters.proxmox import ProxmoxAdapter
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.service import InventoryService
from backend.app.modules.proxmox.schemas import (
    ProxmoxClusterSummaryRead,
    ProxmoxDashboardRead,
    ProxmoxNodeRead,
    ProxmoxVmActionRead,
    ProxmoxVmRead,
)

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
    ) -> None:
        self.adapter = adapter
        self.server_repository = server_repository

    async def get_nodes(self) -> list[ProxmoxNodeRead]:
        raw_nodes = await self.adapter.get_nodes()
        vms = await self.list_vms()
        nodes = self._normalize_nodes(raw_nodes=raw_nodes, vms=vms)
        logger.info("proxmox_nodes_normalized", node_count=len(nodes))
        return nodes

    async def list_vms(self) -> list[ProxmoxVmRead]:
        raw_vms = await self.adapter.list_vms()
        vms = [self._normalize_vm(vm) for vm in raw_vms]
        if self.server_repository is not None:
            vms = await self._add_inventory_context(vms)
        logger.info("proxmox_vms_normalized", vm_count=len(vms))
        return vms

    async def get_vm_status(self, *, node: str, vm_id: int, vm_type: str) -> ProxmoxVmRead:
        raw_status = await self.adapter.get_vm_status(node=node, vm_id=vm_id, vm_type=vm_type)
        return self._normalize_vm({**raw_status, "node": node, "vmid": vm_id, "type": vm_type})

    async def get_cluster_summary(self) -> ProxmoxClusterSummaryRead:
        raw_nodes = await self.adapter.get_nodes()
        vms = await self.list_vms()
        nodes = self._normalize_nodes(raw_nodes=raw_nodes, vms=vms)
        return self._build_summary(nodes=nodes, vms=vms)

    async def get_dashboard(self) -> ProxmoxDashboardRead:
        raw_nodes = await self.adapter.get_nodes()
        vms = await self.list_vms()
        nodes = self._normalize_nodes(raw_nodes=raw_nodes, vms=vms)
        return ProxmoxDashboardRead(
            summary=self._build_summary(nodes=nodes, vms=vms),
            nodes=nodes,
            vms=vms,
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
    ) -> list[ProxmoxNodeRead]:
        vm_counts = Counter(vm.node for vm in vms)
        return [
            cls._normalize_node(node, vm_count=vm_counts.get(str(node.get("node")), 0))
            for node in raw_nodes
        ]

    @staticmethod
    def _normalize_node(raw_node: dict[str, Any], *, vm_count: int) -> ProxmoxNodeRead:
        return ProxmoxNodeRead(
            name=str(raw_node.get("node", "unknown")),
            status=str(raw_node.get("status", "unknown")),
            cpu_usage=_optional_float(raw_node.get("cpu")),
            memory_used=_optional_int(raw_node.get("mem")),
            memory_total=_optional_int(raw_node.get("maxmem")),
            uptime_seconds=_optional_int(raw_node.get("uptime")),
            vm_count=vm_count,
        )

    @staticmethod
    def _normalize_vm(raw_vm: dict[str, Any]) -> ProxmoxVmRead:
        vm_id = _optional_int(raw_vm.get("vmid")) or 0
        vm_type = str(raw_vm.get("type", "unknown"))
        return ProxmoxVmRead(
            vm_id=vm_id,
            name=str(raw_vm.get("name") or raw_vm.get("id") or f"vm-{vm_id}"),
            node=str(raw_vm.get("node", "unknown")),
            type=vm_type,
            status=str(raw_vm.get("status", "unknown")),
            cpu_usage=_optional_float(raw_vm.get("cpu")),
            memory_used=_optional_int(raw_vm.get("mem")),
            memory_total=_optional_int(raw_vm.get("maxmem")),
            disk_used=_optional_int(raw_vm.get("disk")),
            disk_total=_optional_int(raw_vm.get("maxdisk")),
            uptime_seconds=_optional_int(raw_vm.get("uptime")),
            ip_address=_optional_str(
                raw_vm.get("ip")
                or raw_vm.get("ip_address")
                or raw_vm.get("guest_ip")
                or raw_vm.get("agent_ip")
            ),
        )

    async def _add_inventory_context(self, vms: list[ProxmoxVmRead]) -> list[ProxmoxVmRead]:
        if self.server_repository is None:
            return vms

        inventory = await self.server_repository.list_by_provider("proxmox")
        enriched: list[ProxmoxVmRead] = []
        for vm in vms:
            match, sync_status, notes = InventoryService.match_discovered_vm(vm, inventory)
            enriched.append(
                vm.model_copy(
                    update={
                        "inventory_server_id": str(match.id) if match else None,
                        "inventory_hostname": match.hostname if match else None,
                        "inventory_lifecycle_state": match.lifecycle_state.value if match else None,
                        "inventory_sync_status": sync_status.value,
                        "inventory_notes": notes,
                    }
                )
            )
        return enriched

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


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
