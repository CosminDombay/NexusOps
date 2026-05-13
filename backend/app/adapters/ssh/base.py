from abc import abstractmethod
from dataclasses import dataclass

from backend.app.adapters.base import Adapter


@dataclass(frozen=True)
class SshExecutionResult:
    exit_code: int
    stdout: str
    stderr: str


class SshAdapter(Adapter):
    """Remote execution boundary for Linux hosts."""

    @abstractmethod
    async def run_command(
        self,
        *,
        host: str,
        port: int,
        command: str,
        user: str,
        password: str | None = None,
        private_key_path: str | None = None,
    ) -> SshExecutionResult:
        raise NotImplementedError

    @abstractmethod
    async def upload_file(self, host: str, local_path: str, remote_path: str, user: str) -> None:
        raise NotImplementedError
