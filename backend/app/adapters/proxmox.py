from abc import ABC, abstractmethod
from typing import Any

from backend.app.adapters.base import InfrastructureProvider


class ProxmoxAdapter(InfrastructureProvider, ABC):
    """Provider boundary for Proxmox VM lifecycle operations."""

    async def provision_instance(self, payload: dict[str, Any]) -> str:
        return await self.create_vm(payload)

    async def start_instance(self, instance_id: str) -> None:
        await self.start_vm(instance_id)

    async def stop_instance(self, instance_id: str) -> None:
        await self.stop_vm(instance_id)

    async def get_instance_status(self, instance_id: str) -> dict[str, Any]:
        return await self.get_vm_status(instance_id)

    @abstractmethod
    async def create_vm(self, payload: dict[str, Any]) -> str:
        raise NotImplementedError

    @abstractmethod
    async def start_vm(self, vm_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def stop_vm(self, vm_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_vm_status(self, vm_id: str) -> dict[str, Any]:
        raise NotImplementedError
