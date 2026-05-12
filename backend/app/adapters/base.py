from abc import ABC, abstractmethod
from typing import Any


class InfrastructureProvider(ABC):
    """Common contract for infrastructure lifecycle providers."""

    @abstractmethod
    async def provision_instance(self, payload: dict[str, Any]) -> str:
        raise NotImplementedError

    @abstractmethod
    async def start_instance(self, instance_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def stop_instance(self, instance_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_instance_status(self, instance_id: str) -> dict[str, Any]:
        raise NotImplementedError


class SSHProvider(ABC):
    """Common contract for remote command execution providers."""

    @abstractmethod
    async def run_command(self, host: str, command: str, user: str) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def upload_file(self, host: str, local_path: str, remote_path: str, user: str) -> None:
        raise NotImplementedError


class DockerProvider(ABC):
    """Common contract for container orchestration providers."""

    @abstractmethod
    async def deploy_compose(self, host: str, project_name: str, compose_yaml: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def stop_compose(self, host: str, project_name: str) -> None:
        raise NotImplementedError

