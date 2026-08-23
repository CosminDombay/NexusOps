from uuid import uuid4

import pytest

from backend.app.common.constants import (
    InventoryLifecycleState,
    ServerEnvironment,
    ServerSshAuthMethod,
)
from backend.app.modules.auth.models import User, UserRole
from backend.app.modules.inventory.models import Server
from backend.app.modules.remote_access.schemas import RemoteFileWriteResponse
from backend.app.modules.remote_access.service import (
    RemoteAccessDeniedError,
    RemoteAccessService,
    RemoteAccessTargetError,
    RemoteFileConflictError,
    RemotePathError,
)


class FakeServerRepository:
    def __init__(self, server: Server | None) -> None:
        self.server = server

    async def get_by_id(self, server_id):
        if self.server and self.server.id == server_id:
            return self.server
        return None


class FakeRemoteAccessAdapter:
    def __init__(self, *, current_hash: str) -> None:
        self.current_hash = current_hash
        self.writes: list[tuple[str, str, str]] = []

    async def write_file(self, details, path: str, content: str, expected_hash: str):
        if expected_hash != self.current_hash:
            raise RemoteFileConflictError("Remote file changed since it was opened")
        self.writes.append((path, content, expected_hash))
        return RemoteFileWriteResponse(path=path, sha256="b" * 64, size=len(content))


def make_user(role: UserRole, *, superuser: bool = False) -> User:
    return User(
        id=uuid4(),
        username=role.value,
        email=f"{role.value}@example.com",
        password_hash="not-used",
        role=role,
        is_active=True,
        is_superuser=superuser,
    )


def make_server(*, managed: bool = True, archived: bool = False) -> Server:
    return Server(
        id=uuid4(),
        hostname="test-host",
        ip_address="10.0.0.10",
        operating_system="Ubuntu",
        environment=ServerEnvironment.LAB,
        ssh_port=22,
        ssh_username="nexus",
        ssh_auth_method=ServerSshAuthMethod.KEY,
        provider="manual",
        managed=managed,
        lifecycle_state=InventoryLifecycleState.ARCHIVED if archived else InventoryLifecycleState.MANAGED,
    )


def test_viewer_cannot_open_shell() -> None:
    with pytest.raises(RemoteAccessDeniedError):
        RemoteAccessService.require_shell_access(make_user(UserRole.VIEWER))


def test_operator_can_open_shell_authorization_path() -> None:
    RemoteAccessService.require_shell_access(make_user(UserRole.OPERATOR))


def test_admin_can_open_shell_authorization_path() -> None:
    RemoteAccessService.require_shell_access(make_user(UserRole.ADMIN))


def test_file_path_normalization_rejects_traversal() -> None:
    with pytest.raises(RemotePathError):
        RemoteAccessService.normalize_remote_path("/etc/../root/shadow")


@pytest.mark.asyncio
async def test_operator_cannot_write_etc_example_conf() -> None:
    server = make_server()
    service = RemoteAccessService(
        server_repository=FakeServerRepository(server),
        adapter=FakeRemoteAccessAdapter(current_hash="a" * 64),
    )

    with pytest.raises(RemoteAccessDeniedError):
        await service.write_file(server.id, "/etc/example.conf", "content", "a" * 64, make_user(UserRole.OPERATOR))


@pytest.mark.asyncio
async def test_operator_can_write_opt_example_conf() -> None:
    server = make_server()
    adapter = FakeRemoteAccessAdapter(current_hash="a" * 64)
    service = RemoteAccessService(server_repository=FakeServerRepository(server), adapter=adapter)

    result = await service.write_file(
        server.id,
        "/opt/example.conf",
        "content",
        "a" * 64,
        make_user(UserRole.OPERATOR),
    )

    assert result.path == "/opt/example.conf"
    assert adapter.writes == [("/opt/example.conf", "content", "a" * 64)]


@pytest.mark.asyncio
async def test_stale_hash_write_is_rejected() -> None:
    server = make_server()
    service = RemoteAccessService(
        server_repository=FakeServerRepository(server),
        adapter=FakeRemoteAccessAdapter(current_hash="a" * 64),
    )

    with pytest.raises(RemoteFileConflictError):
        await service.write_file(server.id, "/opt/example.conf", "content", "c" * 64, make_user(UserRole.ADMIN))


@pytest.mark.asyncio
async def test_inventory_unmanaged_target_is_rejected() -> None:
    server = make_server(managed=False)
    service = RemoteAccessService(server_repository=FakeServerRepository(server))

    with pytest.raises(RemoteAccessTargetError):
        await service.get_managed_server(server.id)


@pytest.mark.asyncio
async def test_inventory_archived_target_is_rejected() -> None:
    server = make_server(archived=True)
    service = RemoteAccessService(server_repository=FakeServerRepository(server))

    with pytest.raises(RemoteAccessTargetError):
        await service.get_managed_server(server.id)
