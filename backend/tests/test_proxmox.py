from typing import Any

import pytest

from backend.app.adapters.proxmox.base import ProxmoxAdapter
from backend.app.modules.proxmox.service import ProxmoxService, ProxmoxVmActionNotAllowedError


class FakeProxmoxAdapter(ProxmoxAdapter):
    @property
    def name(self) -> str:
        return "fake-proxmox"

    async def get_nodes(self) -> list[dict[str, Any]]:
        return [
            {
                "node": "pve-01",
                "status": "online",
                "cpu": 0.25,
                "mem": 2_147_483_648,
                "maxmem": 8_589_934_592,
                "uptime": 90_000,
            }
        ]

    async def list_vms(self) -> list[dict[str, Any]]:
        return [
            {
                "vmid": 101,
                "name": "app-01",
                "node": "pve-01",
                "type": "qemu",
                "status": "running",
                "cpu": 0.1,
                "mem": 536_870_912,
                "maxmem": 2_147_483_648,
                "uptime": 3_600,
            },
            {
                "vmid": 102,
                "name": "db-01",
                "node": "pve-01",
                "type": "qemu",
                "status": "stopped",
            },
        ]

    async def get_vm_status(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        return {
            "vmid": vm_id,
            "name": "app-01",
            "node": node,
            "type": vm_type,
            "status": "running",
        }

    async def get_cluster_summary(self) -> dict[str, Any]:
        return {"resources": []}

    async def start_vm(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        return {"task_id": f"UPID:{node}:{vm_type}:{vm_id}:start"}

    async def stop_vm(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        return {"task_id": f"UPID:{node}:{vm_type}:{vm_id}:stop"}

    async def reboot_vm(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        return {"task_id": f"UPID:{node}:{vm_type}:{vm_id}:reboot"}

    async def shutdown_vm(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        return {"task_id": f"UPID:{node}:{vm_type}:{vm_id}:shutdown"}


@pytest.mark.asyncio
async def test_proxmox_dashboard_normalizes_cluster_state() -> None:
    dashboard = await ProxmoxService(FakeProxmoxAdapter()).get_dashboard()

    assert dashboard.summary.node_count == 1
    assert dashboard.summary.vm_count == 2
    assert dashboard.summary.running_vm_count == 1
    assert dashboard.summary.stopped_vm_count == 1
    assert dashboard.nodes[0].name == "pve-01"
    assert dashboard.nodes[0].vm_count == 2
    assert dashboard.vms[0].vm_id == 101


@pytest.mark.asyncio
async def test_proxmox_start_action_resolves_stopped_vm() -> None:
    action = await ProxmoxService(FakeProxmoxAdapter()).start_vm(102)

    assert action.vm_id == 102
    assert action.action == "start"
    assert action.status == "accepted"
    assert action.task_id == "UPID:pve-01:qemu:102:start"


@pytest.mark.asyncio
async def test_proxmox_reboot_requires_running_vm() -> None:
    with pytest.raises(ProxmoxVmActionNotAllowedError):
        await ProxmoxService(FakeProxmoxAdapter()).reboot_vm(102)
