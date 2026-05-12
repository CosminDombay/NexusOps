from abc import ABC, abstractmethod


class SshExecutionResult:
    def __init__(self, exit_code: int, stdout: str, stderr: str) -> None:
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr


class SshAdapter(ABC):
    """Remote execution boundary for Linux hosts."""

    @abstractmethod
    async def run_command(self, host: str, command: str, user: str) -> SshExecutionResult:
        raise NotImplementedError

    @abstractmethod
    async def upload_file(self, host: str, local_path: str, remote_path: str, user: str) -> None:
        raise NotImplementedError

