import asyncio
from pathlib import Path

import paramiko
import structlog

from backend.app.adapters.ssh.base import SshAdapter, SshExecutionResult
from backend.app.core.config import settings

logger = structlog.get_logger(__name__)


class SshConnectionError(Exception):
    """Raised when a remote host cannot be reached over SSH."""


class ParamikoSshAdapter(SshAdapter):
    """Paramiko-backed SSH command execution adapter."""

    @property
    def name(self) -> str:
        return "paramiko-ssh"

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
        return await asyncio.to_thread(
            self._run_command_sync,
            host=host,
            port=port,
            command=command,
            user=user,
            password=password,
            private_key_path=private_key_path,
        )

    async def upload_file(self, host: str, local_path: str, remote_path: str, user: str) -> None:
        raise NotImplementedError("File upload is outside the SSH execution MVP")

    def _run_command_sync(
        self,
        *,
        host: str,
        port: int,
        command: str,
        user: str,
        password: str | None,
        private_key_path: str | None,
    ) -> SshExecutionResult:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        key_filename = self._key_filename(private_key_path)
        use_password = password is not None

        try:
            client.connect(
                hostname=host,
                port=port,
                username=user,
                password=password,
                key_filename=key_filename,
                timeout=settings.ssh_connect_timeout_seconds,
                look_for_keys=not use_password,
                allow_agent=not use_password,
            )
            _, stdout_stream, stderr_stream = client.exec_command(
                command,
                timeout=settings.ssh_command_timeout_seconds,
            )
            stdout = stdout_stream.read().decode("utf-8", errors="replace")
            stderr = stderr_stream.read().decode("utf-8", errors="replace")
            exit_code = stdout_stream.channel.recv_exit_status()
        except Exception as exc:
            logger.warning(
                "ssh_command_failed",
                host=host,
                port=port,
                user=user,
                command=command,
                reason=exc.__class__.__name__,
            )
            raise SshConnectionError(f"SSH command failed for {host}: {exc}") from exc
        finally:
            client.close()

        logger.info("ssh_command_completed", host=host, port=port, user=user, exit_code=exit_code)
        return SshExecutionResult(exit_code=exit_code, stdout=stdout, stderr=stderr)

    @staticmethod
    def _key_filename(private_key_path: str | None) -> str | None:
        selected_path = private_key_path or settings.ssh_private_key_path
        if not selected_path:
            return None
        return str(Path(selected_path).expanduser())
