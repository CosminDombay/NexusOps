from abc import abstractmethod
from typing import Any

from backend.app.adapters.base import Adapter


class ProxmoxAdapter(Adapter):
    """Read-only boundary for Proxmox infrastructure discovery."""

    @abstractmethod
    async def get_nodes(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def list_vms(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def get_vm_status(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_cluster_summary(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def start_vm(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def stop_vm(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def reboot_vm(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def shutdown_vm(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        raise NotImplementedError
