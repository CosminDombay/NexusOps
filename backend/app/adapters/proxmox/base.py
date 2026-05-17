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
    async def list_vm_templates(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def get_vm_status(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        raise NotImplementedError

    async def get_vm_network_interfaces(self, *, node: str, vm_id: int, vm_type: str) -> list[dict[str, Any]]:
        return []

    @abstractmethod
    async def get_cluster_summary(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_task_status(self, *, node: str, task_id: str) -> dict[str, Any]:
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

    @abstractmethod
    async def clone_vm_template(
        self,
        *,
        node: str,
        template_id: int,
        new_vm_id: int,
        name: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def configure_cloud_init(
        self,
        *,
        node: str,
        vm_id: int,
        cpu_cores: int,
        memory_mb: int,
        network_bridge: str,
        username: str,
        password: str | None,
        ssh_public_key: str | None,
        ip_cidr: str,
        gateway: str,
        dns_servers: list[str],
        start_on_boot: bool,
        description: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def resize_vm_disk(
        self,
        *,
        node: str,
        vm_id: int,
        disk_size_gb: int,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def add_vm_disk(
        self,
        *,
        node: str,
        vm_id: int,
        disk: str,
        storage: str,
        size_gb: int,
    ) -> dict[str, Any]:
        raise NotImplementedError
