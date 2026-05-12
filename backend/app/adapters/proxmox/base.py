from abc import abstractmethod
from typing import Any

from backend.app.adapters.base import Adapter


class ProxmoxAdapter(Adapter):
    """Provider boundary for Proxmox VM lifecycle operations."""

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
