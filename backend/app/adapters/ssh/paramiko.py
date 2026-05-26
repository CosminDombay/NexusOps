import asyncio
import io
import hashlib
from pathlib import Path

import paramiko
import structlog

from backend.app.adapters.ssh.base import SshAdapter, SshExecutionResult
from backend.app.core.config import settings

logger = structlog.get_logger(__name__)


class SshConnectionError(Exception):
    """Raised when a remote host cannot be reached over SSH."""


class TrustOnFirstUsePolicy(paramiko.MissingHostKeyPolicy):
    def missing_host_key(self, client: paramiko.SSHClient, hostname: str, key: paramiko.PKey) -> None:
        if not settings.ssh_trust_on_first_use:
            raise SshConnectionError("SSH host key is not trusted")
        fingerprint = "SHA256:" + hashlib.sha256(key.asbytes()).hexdigest()
        logger.warning("ssh_host_key_trusted_on_first_use", host=hostname, fingerprint=fingerprint)
        client.get_host_keys().add(hostname, key.get_name(), key)


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
    ) -> SshExecutionResult:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(TrustOnFirstUsePolicy())
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

    @staticmethod
    def _pkey(private_key: str | None, passphrase: str | None) -> paramiko.PKey | None:
        if not private_key:
            return None
        key_stream = io.StringIO(private_key)
        loaders = (
            paramiko.RSAKey.from_private_key,
            paramiko.Ed25519Key.from_private_key,
            paramiko.ECDSAKey.from_private_key,
            paramiko.DSSKey.from_private_key,
        )
        for loader in loaders:
            key_stream.seek(0)
            try:
                return loader(key_stream, password=passphrase)
            except paramiko.SSHException:
                continue
        raise SshConnectionError("Unsupported SSH private key format")
