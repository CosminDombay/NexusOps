from abc import ABC, abstractmethod


class DockerComposeAdapter(ABC):
    """Boundary for Docker Compose operations on managed servers."""

    @abstractmethod
    async def deploy_compose(self, host: str, project_name: str, compose_yaml: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def stop_compose(self, host: str, project_name: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_compose_status(self, host: str, project_name: str) -> dict[str, str]:
        raise NotImplementedError

