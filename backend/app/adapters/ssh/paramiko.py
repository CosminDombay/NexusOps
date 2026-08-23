import asyncio
from pathlib import Path

import paramiko
import structlog

from backend.app.adapters.ssh.base import SshAdapter, SshExecutionResult
from backend.app.adapters.ssh.host_keys import HostKeyPolicy, HostKeyVerificationError
from backend.app.adapters.ssh.keys import PrivateKeyLoadError, load_private_key
from backend.app.core.config import settings

logger = structlog.get_logger(__name__)


class SshConnectionError(Exception):
    """Raised when a remote host cannot be reached over SSH."""


class SshHostKeyError(SshConnectionError):
    """Raised when a host key is untrusted or does not match the pinned fingerprint."""


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
        private_key: str | None = None,
        passphrase: str | None = None,
        input_data: str | None = None,
        host_key_policy: HostKeyPolicy | None = None,
    ) -> SshExecutionResult:
        return await asyncio.to_thread(
            self._run_command_sync,
            host=host,
            port=port,
            command=command,
            user=user,
            password=password,
            private_key_path=private_key_path,
            private_key=private_key,
            passphrase=passphrase,
            input_data=input_data,
            host_key_policy=host_key_policy,
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
        private_key: str | None,
        passphrase: str | None,
        input_data: str | None,
        host_key_policy: HostKeyPolicy | None = None,
    ) -> SshExecutionResult:
        client = paramiko.SSHClient()
        policy = host_key_policy or HostKeyPolicy(
            None, trust_on_first_use=settings.ssh_trust_on_first_use
        )
        client.set_missing_host_key_policy(policy)
        key_filename = self._key_filename(private_key_path)
        use_password = password is not None
        use_inline_key = private_key is not None

        try:
            client.connect(
                hostname=host,
                port=port,
                username=user,
                password=password,
                pkey=self._pkey(private_key, passphrase),
                key_filename=key_filename,
                timeout=settings.ssh_connect_timeout_seconds,
                look_for_keys=not use_password and not use_inline_key,
                allow_agent=not use_password and not use_inline_key,
            )
            stdin_stream, stdout_stream, stderr_stream = client.exec_command(
                command,
                timeout=settings.ssh_command_timeout_seconds,
            )
            if input_data:
                stdin_stream.write(input_data)
                stdin_stream.flush()
                stdin_stream.channel.shutdown_write()
            stdout = stdout_stream.read().decode("utf-8", errors="replace")
            stderr = stderr_stream.read().decode("utf-8", errors="replace")
            exit_code = stdout_stream.channel.recv_exit_status()
        except HostKeyVerificationError as exc:
            # Never retried or downgraded: a mismatch means the peer is not the host we pinned.
            logger.warning("ssh_host_key_rejected", host=host, port=port, user=user)
            raise SshHostKeyError(str(exc)) from exc
        except Exception as exc:
            # The command is deliberately not logged: resolved templates can carry
            # credential-backed values.
            logger.warning(
                "ssh_command_failed",
                host=host,
                port=port,
                user=user,
                reason=exc.__class__.__name__,
            )
            raise SshConnectionError(f"SSH command failed for {host}: {exc}") from exc
        finally:
            client.close()

        logger.info("ssh_command_completed", host=host, port=port, user=user, exit_code=exit_code)
        return SshExecutionResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            accepted_host_key_sha256=policy.accepted_fingerprint,
        )

    @staticmethod
    def _key_filename(private_key_path: str | None) -> str | None:
        selected_path = private_key_path or settings.ssh_private_key_path
        if not selected_path:
            return None
        return str(Path(selected_path).expanduser())

    @staticmethod
    def _pkey(private_key: str | None, passphrase: str | None) -> paramiko.PKey | None:
        try:
            return load_private_key(private_key, passphrase)
        except PrivateKeyLoadError as exc:
            raise SshConnectionError(str(exc)) from exc
