from abc import abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.app.adapters.base import Adapter

if TYPE_CHECKING:
    from backend.app.adapters.ssh.host_keys import HostKeyPolicy


@dataclass(frozen=True)
class SshExecutionResult:
    exit_code: int
    stdout: str
    stderr: str
    accepted_host_key_sha256: str | None = None


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
        private_key: str | None = None,
        passphrase: str | None = None,
        input_data: str | None = None,
        host_key_policy: "HostKeyPolicy | None" = None,
    ) -> SshExecutionResult:
        raise NotImplementedError

    @abstractmethod
    async def upload_file(self, host: str, local_path: str, remote_path: str, user: str) -> None:
        raise NotImplementedError
