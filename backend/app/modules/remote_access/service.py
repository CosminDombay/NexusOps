import asyncio
import hashlib
import io
import posixpath
import stat
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from uuid import UUID

import paramiko

from backend.app.core.config import settings
from backend.app.modules.auth.models import User, UserRole
from backend.app.modules.credentials.service import CredentialNotFoundError, CredentialService
from backend.app.modules.inventory.models import InventoryLifecycleState, Server, ServerSshAuthMethod
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.remote_access.schemas import (
    RemoteDirectoryListing,
    RemoteFileEntry,
    RemoteFileRead,
    RemoteFileType,
    RemoteFileWriteResponse,
)


class RemoteAccessError(Exception):
    """Base remote access error."""


class RemoteAccessDeniedError(RemoteAccessError):
    """Raised when a user role cannot perform an operation."""


class RemoteAccessTargetError(RemoteAccessError):
    """Raised when a host is not a valid managed inventory target."""


class RemotePathError(RemoteAccessError):
    """Raised when a remote path is invalid or outside policy."""


class RemoteFileConflictError(RemoteAccessError):
    """Raised when a write would overwrite stale content."""


class RemoteSshError(RemoteAccessError):
    """Raised when SSH/SFTP operations fail."""


@dataclass(frozen=True)
class SshConnectionDetails:
    host: str
    port: int
    username: str
    password: str | None = None
    private_key_path: str | None = None
    private_key: str | None = None
    passphrase: str | None = None
    trusted_host_key_sha256: str | None = None
    trust_on_first_use: bool = True


@dataclass
class ShellSession:
    client: paramiko.SSHClient
    channel: paramiko.Channel

    def close(self) -> None:
        try:
            self.channel.close()
        finally:
            self.client.close()


class ParamikoRemoteAccessAdapter:
    """Paramiko-backed shell and SFTP adapter for remote access."""

    def __init__(self) -> None:
        self.last_accepted_host_key_sha256: str | None = None

    async def open_shell(self, details: SshConnectionDetails) -> ShellSession:
        return await asyncio.to_thread(self._open_shell_sync, details)

    async def list_directory(
        self,
        details: SshConnectionDetails,
        path: str,
    ) -> RemoteDirectoryListing:
        return await asyncio.to_thread(self._list_directory_sync, details, path)

    async def read_file(self, details: SshConnectionDetails, path: str) -> RemoteFileRead:
        return await asyncio.to_thread(self._read_file_sync, details, path)

    async def write_file(
        self,
        details: SshConnectionDetails,
        path: str,
        content: str,
        expected_hash: str,
    ) -> RemoteFileWriteResponse:
        return await asyncio.to_thread(self._write_file_sync, details, path, content, expected_hash)

    def _open_shell_sync(self, details: SshConnectionDetails) -> ShellSession:
        client = self._connect(details)
        try:
            channel = client.invoke_shell(term="xterm-256color", width=120, height=32)
        except Exception:
            client.close()
            raise
        return ShellSession(client=client, channel=channel)

    def _list_directory_sync(self, details: SshConnectionDetails, path: str) -> RemoteDirectoryListing:
        with self._sftp(details) as sftp:
            entries = []
            for attrs in sftp.listdir_attr(path):
                entry_path = posixpath.join(path.rstrip("/") or "/", attrs.filename)
                entries.append(self._entry_from_attrs(attrs.filename, entry_path, attrs))
            entries.sort(key=lambda item: (item.type != RemoteFileType.DIRECTORY, item.name.lower()))
            return RemoteDirectoryListing(path=path, entries=entries)

    def _read_file_sync(self, details: SshConnectionDetails, path: str) -> RemoteFileRead:
        with self._sftp(details) as sftp:
            attrs = sftp.stat(path)
            with sftp.open(path, "rb") as handle:
                raw = handle.read()
            content = raw.decode("utf-8", errors="replace")
            return RemoteFileRead(
                path=path,
                content=content,
                sha256=hashlib.sha256(raw).hexdigest(),
                size=len(raw),
                modified_at=self._modified_at(attrs),
            )

    def _write_file_sync(
        self,
        details: SshConnectionDetails,
        path: str,
        content: str,
        expected_hash: str,
    ) -> RemoteFileWriteResponse:
        raw = content.encode("utf-8")
        with self._sftp(details) as sftp:
            try:
                current = self._read_existing_bytes(sftp, path)
            except FileNotFoundError:
                current = b""
            current_hash = hashlib.sha256(current).hexdigest()
            if current_hash != expected_hash:
                raise RemoteFileConflictError("Remote file changed since it was opened")

            temp_path = f"{path}.nexusops-{int(time.time() * 1000)}.tmp"
            with sftp.open(temp_path, "wb") as handle:
                handle.write(raw)
            try:
                sftp.posix_rename(temp_path, path)
            except (AttributeError, OSError):
                sftp.rename(temp_path, path)
            attrs = sftp.stat(path)
            return RemoteFileWriteResponse(
                path=path,
                sha256=hashlib.sha256(raw).hexdigest(),
                size=len(raw),
                modified_at=self._modified_at(attrs),
            )

    def _connect(self, details: SshConnectionDetails) -> paramiko.SSHClient:
        client = paramiko.SSHClient()
        policy = FingerprintPolicy(details.trusted_host_key_sha256, details.trust_on_first_use)
        client.set_missing_host_key_policy(policy)
        try:
            client.connect(
                hostname=details.host,
                port=details.port,
                username=details.username,
                password=details.password,
                pkey=self._pkey(details),
                key_filename=self._key_filename(details.private_key_path),
                timeout=settings.ssh_connect_timeout_seconds,
                look_for_keys=details.password is None and details.private_key is None,
                allow_agent=details.password is None and details.private_key is None,
            )
            if policy.accepted_fingerprint:
                self.last_accepted_host_key_sha256 = policy.accepted_fingerprint
            return client
        except Exception as exc:
            client.close()
            raise RemoteSshError(f"SSH connection failed for {details.host}: {exc}") from exc

    @contextmanager
    def _sftp(self, details: SshConnectionDetails):
        client = self._connect(details)
        sftp = None
        try:
            sftp = client.open_sftp()
            yield sftp
        finally:
            if sftp is not None:
                sftp.close()
            client.close()

    @staticmethod
    def _read_existing_bytes(sftp: paramiko.SFTPClient, path: str) -> bytes:
        with sftp.open(path, "rb") as handle:
            return handle.read()

    @staticmethod
    def _key_filename(private_key_path: str | None) -> str | None:
        selected_path = private_key_path or settings.ssh_private_key_path
        if not selected_path:
            return None
        return str(Path(selected_path).expanduser())

    @staticmethod
    def _pkey(details: SshConnectionDetails) -> paramiko.PKey | None:
        if not details.private_key:
            return None
        key_stream = io.StringIO(details.private_key)
        loaders = (
            paramiko.RSAKey.from_private_key,
            paramiko.Ed25519Key.from_private_key,
            paramiko.ECDSAKey.from_private_key,
            paramiko.DSSKey.from_private_key,
        )
        for loader in loaders:
            key_stream.seek(0)
            try:
                return loader(key_stream, password=details.passphrase)
            except paramiko.SSHException:
                continue
        raise RemoteSshError("Unsupported SSH private key format")

    @staticmethod
    def _entry_from_attrs(name: str, path: str, attrs: paramiko.SFTPAttributes) -> RemoteFileEntry:
        mode = attrs.st_mode or 0
        if stat.S_ISDIR(mode):
            file_type = RemoteFileType.DIRECTORY
        elif stat.S_ISREG(mode):
            file_type = RemoteFileType.FILE
        elif stat.S_ISLNK(mode):
            file_type = RemoteFileType.SYMLINK
        else:
            file_type = RemoteFileType.OTHER
        return RemoteFileEntry(
            name=name,
            path=path,
            type=file_type,
            size=attrs.st_size or 0,
            modified_at=ParamikoRemoteAccessAdapter._modified_at(attrs),
            permissions=stat.filemode(mode),
            owner=str(attrs.st_uid) if attrs.st_uid is not None else None,
            group=str(attrs.st_gid) if attrs.st_gid is not None else None,
        )

    @staticmethod
    def _modified_at(attrs: paramiko.SFTPAttributes) -> datetime | None:
        return datetime.fromtimestamp(attrs.st_mtime, UTC) if attrs.st_mtime else None


class RemoteAccessService:
    OPERATOR_WRITE_PREFIXES = ("/opt", "/srv", "/var/www", "/home")

    def __init__(
        self,
        *,
        server_repository: ServerRepository,
        credential_service: CredentialService | None = None,
        adapter: ParamikoRemoteAccessAdapter | None = None,
    ) -> None:
        self.server_repository = server_repository
        self.credential_service = credential_service
        self.adapter = adapter or ParamikoRemoteAccessAdapter()

    async def open_shell(self, server_id: UUID, user: User) -> ShellSession:
        self.require_shell_access(user)
        server = await self.get_managed_server(server_id)
        shell = await self.adapter.open_shell(await self.resolve_ssh_details(server))
        await self.persist_trusted_host_key(server)
        return shell

    async def list_files(self, server_id: UUID, path: str, user: User) -> RemoteDirectoryListing:
        self.require_file_read_access(user)
        server = await self.get_managed_server(server_id)
        normalized = self.normalize_remote_path(path)
        result = await self.adapter.list_directory(await self.resolve_ssh_details(server), normalized)
        await self.persist_trusted_host_key(server)
        return result

    async def read_file(self, server_id: UUID, path: str, user: User) -> RemoteFileRead:
        self.require_file_read_access(user)
        server = await self.get_managed_server(server_id)
        normalized = self.normalize_remote_path(path)
        result = await self.adapter.read_file(await self.resolve_ssh_details(server), normalized)
        await self.persist_trusted_host_key(server)
        return result

    async def write_file(
        self,
        server_id: UUID,
        path: str,
        content: str,
        expected_hash: str,
        user: User,
    ) -> RemoteFileWriteResponse:
        self.require_file_write_access(user)
        normalized = self.normalize_remote_path(path)
        self.require_write_path(user, normalized)
        server = await self.get_managed_server(server_id)
        result = await self.adapter.write_file(
            await self.resolve_ssh_details(server),
            normalized,
            content,
            self.normalize_expected_hash(expected_hash),
        )
        await self.persist_trusted_host_key(server)
        return result

    async def persist_trusted_host_key(self, server: Server) -> None:
        fingerprint = getattr(self.adapter, "last_accepted_host_key_sha256", None)
        if fingerprint and not server.trusted_ssh_host_key_sha256:
            server.trusted_ssh_host_key_sha256 = fingerprint
            server.trusted_ssh_host_key_accepted_at = datetime.now(UTC)
            await self.server_repository.session.commit()

    async def get_managed_server(self, server_id: UUID) -> Server:
        server = await self.server_repository.get_by_id(server_id)
        if server is None:
            raise RemoteAccessTargetError("Inventory server not found")
        if not server.managed or server.lifecycle_state in {
            InventoryLifecycleState.ARCHIVED,
            InventoryLifecycleState.DECOMMISSIONED,
            InventoryLifecycleState.DELETED,
        }:
            raise RemoteAccessTargetError("Inventory server is not managed")
        return server

    async def resolve_ssh_details(self, server: Server) -> SshConnectionDetails:
        username = server.ssh_username
        password = server.ssh_password if server.ssh_auth_method == ServerSshAuthMethod.PASSWORD else None
        private_key_path = (
            server.ssh_private_key_path if server.ssh_auth_method == ServerSshAuthMethod.KEY else None
        )
        private_key: str | None = None
        passphrase: str | None = None

        if server.credential_id is not None:
            if self.credential_service is None:
                raise CredentialNotFoundError("Credential service is required for credential-backed remote access")
            credential = await self.credential_service.resolve_credential(server.credential_id)
            username = credential.username or username
            if credential.credential_type in {"password", "ssh_password"}:
                password = credential.secret
                private_key_path = None
            elif credential.credential_type == "ssh_key":
                password = None
                private_key = credential.private_key
                passphrase = credential.passphrase

        return SshConnectionDetails(
            host=server.ip_address,
            port=server.ssh_port,
            username=username,
            password=password,
            private_key_path=private_key_path,
            private_key=private_key,
            passphrase=passphrase,
            trusted_host_key_sha256=server.trusted_ssh_host_key_sha256,
            trust_on_first_use=settings.ssh_trust_on_first_use,
        )

    @staticmethod
    def require_shell_access(user: User) -> None:
        if user.is_superuser or user.role in {UserRole.ADMIN, UserRole.OPERATOR}:
            return
        raise RemoteAccessDeniedError("Shell access requires operator or admin role")

    @staticmethod
    def require_file_read_access(user: User) -> None:
        if user.is_superuser or user.role in {UserRole.ADMIN, UserRole.OPERATOR}:
            return
        raise RemoteAccessDeniedError("File access requires operator or admin role")

    @staticmethod
    def require_file_write_access(user: User) -> None:
        if user.is_superuser or user.role in {UserRole.ADMIN, UserRole.OPERATOR}:
            return
        raise RemoteAccessDeniedError("File editing requires operator or admin role")

    @classmethod
    def require_write_path(cls, user: User, path: str) -> None:
        if user.is_superuser or user.role == UserRole.ADMIN:
            return
        if user.role == UserRole.OPERATOR and any(
            path == prefix or path.startswith(f"{prefix}/") for prefix in cls.OPERATOR_WRITE_PREFIXES
        ):
            return
        raise RemoteAccessDeniedError("Operators can edit files only under /opt, /srv, /var/www, or /home")

    @staticmethod
    def normalize_remote_path(path: str) -> str:
        raw = path.strip()
        if not raw:
            raise RemotePathError("Path is required")
        if "\x00" in raw:
            raise RemotePathError("Path contains invalid characters")
        if not raw.startswith("/"):
            raise RemotePathError("Path must be absolute")
        if ".." in PurePosixPath(raw).parts:
            raise RemotePathError("Path traversal is not allowed")
        normalized = posixpath.normpath(raw)
        if normalized in {"", "."}:
            raise RemotePathError("Path is required")
        return normalized

    @staticmethod
    def normalize_expected_hash(expected_hash: str) -> str:
        value = expected_hash.strip().lower()
        if value.startswith("sha256:"):
            value = value.removeprefix("sha256:")
        elif value.startswith("sha256") and len(value) == 70:
            value = value.removeprefix("sha256")
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise RemotePathError("expected_hash must be a SHA-256 hex digest")
        return value


def host_key_fingerprint_sha256(key: paramiko.PKey) -> str:
    return "SHA256:" + hashlib.sha256(key.asbytes()).hexdigest()


class FingerprintPolicy(paramiko.MissingHostKeyPolicy):
    def __init__(self, expected_fingerprint: str | None, trust_on_first_use: bool) -> None:
        self.expected_fingerprint = expected_fingerprint
        self.trust_on_first_use = trust_on_first_use
        self.accepted_fingerprint: str | None = None

    def missing_host_key(self, client: paramiko.SSHClient, hostname: str, key: paramiko.PKey) -> None:
        fingerprint = host_key_fingerprint_sha256(key)
        if self.expected_fingerprint and fingerprint != self.expected_fingerprint:
            raise RemoteSshError("SSH host key fingerprint mismatch")
        if not self.expected_fingerprint and not self.trust_on_first_use:
            raise RemoteSshError("SSH host key is not trusted")
        self.accepted_fingerprint = fingerprint
        client.get_host_keys().add(hostname, key.get_name(), key)
