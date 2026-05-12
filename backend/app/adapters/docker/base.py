from abc import abstractmethod

from backend.app.adapters.base import Adapter


class DockerComposeAdapter(Adapter):
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
