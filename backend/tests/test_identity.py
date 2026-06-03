from typing import Any

import pytest
from pydantic import ValidationError

from backend.app.adapters.ssh import SshAdapter, SshExecutionResult
from backend.app.modules.credentials.schemas import ResolvedCredential
from backend.app.modules.identity.models import LinuxUser
from backend.app.modules.identity.repository import IdentityExecutionRepository, LinuxGroupRepository, LinuxUserRepository
from backend.app.modules.identity.schemas import LinuxGroupCreate, LinuxGroupUpdate, LinuxUserCreate, LinuxUserUpdate, ReplicationRequest
from backend.app.modules.identity.service import IdentityReplicationService, IdentityValidationError, LinuxGroupService, LinuxUserService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.schemas import ServerCreate
from backend.app.modules.inventory.service import InventoryService
from backend.app.modules.jobs.repository import JobRepository
from backend.app.modules.jobs.service import JobService


class FakeSshAdapter(SshAdapter):
    def __init__(self, *, stdout: str = "identity ok\n") -> None:
        self.calls: list[dict[str, Any]] = []
        self.stdout = stdout

    @property
    def name(self) -> str:
        return "fake-identity-ssh"

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
    ) -> SshExecutionResult:
        self.calls.append({"host": host, "command": command, "user": user, "input_data": input_data})
        return SshExecutionResult(exit_code=0, stdout=self.stdout, stderr="")

    async def upload_file(self, host: str, local_path: str, remote_path: str, user: str) -> None:
        raise NotImplementedError


class FakeCredentialService:
    async def resolve_credential(self, credential_id_or_name):
        return ResolvedCredential(
            id="11111111-1111-1111-1111-111111111111",
            name=str(credential_id_or_name),
            credential_type="password",
            secret="SuperSecret123!",
        )


def server_payload(**overrides):
    payload = {
        "hostname": "identity-target-01",
        "ip_address": "10.4.0.10",
        "operating_system": "Ubuntu 24.04 LTS",
        "environment": "lab",
        "provider": "manual",
        "ssh_port": 22,
        "ssh_username": "ubuntu",
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_linux_user_replication_uses_jobs_pipeline(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(**server_payload())
        )
        adapter = FakeSshAdapter()
        job_service = JobService(
            job_repository=JobRepository(db_session),
            server_repository=ServerRepository(db_session),
            ssh_adapter=adapter,
        )
        service = LinuxUserService(
            repository=LinuxUserRepository(db_session),
            replication_service=IdentityReplicationService(
                job_service=job_service,
                execution_repository=IdentityExecutionRepository(db_session),
            ),
        )
        created = await service.create_user(
            LinuxUserCreate(username="deploy", sudo_enabled=True, sudo_nopasswd=True)
        )

        result = await service.replicate_user(
            created.item.id,
            ReplicationRequest(target_server_ids=[server.id]),
        )

        assert result.success_count == 1
        assert result.failure_count == 0
        assert "useradd" in adapter.calls[0]["command"]
        assert "visudo -cf" in adapter.calls[0]["command"]


@pytest.mark.asyncio
async def test_linux_user_password_credential_is_redacted_in_job_history(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(**server_payload(hostname="identity-target-02", ip_address="10.4.0.12"))
        )
        adapter = FakeSshAdapter()
        service = LinuxUserService(
            repository=LinuxUserRepository(db_session),
            replication_service=IdentityReplicationService(
                job_service=JobService(
                    job_repository=JobRepository(db_session),
                    server_repository=ServerRepository(db_session),
                    ssh_adapter=adapter,
                    credential_service=FakeCredentialService(),
                ),
                execution_repository=IdentityExecutionRepository(db_session),
            ),
            credential_service=FakeCredentialService(),
        )

        created = await service.create_user(
            LinuxUserCreate(
                username="deploy",
                password_credential_ref="deploy-password",
                target_server_ids=[server.id],
            )
        )

        job = created.replication.results[0].job
        assert "SuperSecret123!" in adapter.calls[0]["command"]
        assert "chpasswd" in adapter.calls[0]["command"]
        assert job is not None
        assert "SuperSecret123!" not in job.command
        assert "deploy:********" in job.command


def test_identity_router_lists_users(client) -> None:
    response = client.get("/api/v1/identity/users")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_identity_discovery_parses_existing_users_and_groups(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(**server_payload(hostname="discover-identity-01", ip_address="10.4.0.11"))
        )
        user_adapter = FakeSshAdapter(
            stdout=(
                "root:x:0:0:root:/root:/bin/bash\n"
                "deploy:x:1001:1001::/home/deploy:/bin/bash\n"
                "daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin\n"
            )
        )
        user_discovery = await IdentityReplicationService(
            job_service=JobService(
                job_repository=JobRepository(db_session),
                server_repository=ServerRepository(db_session),
                ssh_adapter=user_adapter,
            ),
            execution_repository=IdentityExecutionRepository(db_session),
        ).discover_users([server.id])

        group_adapter = FakeSshAdapter(stdout="docker:x:998:deploy\nwww-data:x:33:\n")
        group_discovery = await IdentityReplicationService(
            job_service=JobService(
                job_repository=JobRepository(db_session),
                server_repository=ServerRepository(db_session),
                ssh_adapter=group_adapter,
            ),
            execution_repository=IdentityExecutionRepository(db_session),
        ).discover_groups([server.id])

        assert [user.username for user in user_discovery.users] == ["deploy"]
        assert user_discovery.users[0].home_directory == "/home/deploy"
        assert any(group.name == "docker" for group in group_discovery.groups)
        docker = next(group for group in group_discovery.groups if group.name == "docker")
        assert docker.members == ["deploy"]


def test_identity_rejects_root_as_managed_user() -> None:
    with pytest.raises(ValidationError):
        LinuxUserCreate(username="root")


@pytest.mark.asyncio
async def test_identity_rejects_root_group_inspection(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(**server_payload(hostname="root-inspect-identity-01", ip_address="10.4.0.16"))
        )
        service = IdentityReplicationService(
            job_service=JobService(
                job_repository=JobRepository(db_session),
                server_repository=ServerRepository(db_session),
                ssh_adapter=FakeSshAdapter(),
            ),
            execution_repository=IdentityExecutionRepository(db_session),
        )

        with pytest.raises(IdentityValidationError):
            await service.discover_user_groups("root", [server.id])


@pytest.mark.asyncio
async def test_identity_rejects_remote_operations_for_existing_root_record(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(**server_payload(hostname="root-action-identity-01", ip_address="10.4.0.17"))
        )
        root_user = await LinuxUserRepository(db_session).create(
            LinuxUser(username="root", shell="/bin/bash", home_directory="/root")
        )
        await db_session.commit()
        service = LinuxUserService(
            repository=LinuxUserRepository(db_session),
            replication_service=IdentityReplicationService(
                job_service=JobService(
                    job_repository=JobRepository(db_session),
                    server_repository=ServerRepository(db_session),
                    ssh_adapter=FakeSshAdapter(),
                ),
                execution_repository=IdentityExecutionRepository(db_session),
            ),
        )

        with pytest.raises(IdentityValidationError):
            await service.replicate_user(root_user.id, ReplicationRequest(target_server_ids=[server.id]))


@pytest.mark.asyncio
async def test_identity_can_inspect_user_groups(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(**server_payload(hostname="membership-identity-01", ip_address="10.4.0.13"))
        )
        adapter = FakeSshAdapter(stdout="cerberus docker www-data sudo\n")

        membership = await IdentityReplicationService(
            job_service=JobService(
                job_repository=JobRepository(db_session),
                server_repository=ServerRepository(db_session),
                ssh_adapter=adapter,
            ),
            execution_repository=IdentityExecutionRepository(db_session),
        ).discover_user_groups("cerberus", [server.id])

        assert adapter.calls[0]["command"] == "id -nG cerberus"
        assert membership.hosts[0].groups == ["cerberus", "docker", "sudo", "www-data"]


@pytest.mark.asyncio
async def test_identity_can_inspect_group_members_including_primary_group_users(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(**server_payload(hostname="group-membership-identity-01", ip_address="10.4.0.15"))
        )
        adapter = FakeSshAdapter(
            stdout=(
                "cerberus:x:1001:deploy\n"
                "root:x:0:0:root:/root:/bin/bash\n"
                "cerberus:x:1001:1001::/home/cerberus:/bin/bash\n"
                "deploy:x:1002:1002::/home/deploy:/bin/bash\n"
            )
        )

        membership = await IdentityReplicationService(
            job_service=JobService(
                job_repository=JobRepository(db_session),
                server_repository=ServerRepository(db_session),
                ssh_adapter=adapter,
            ),
            execution_repository=IdentityExecutionRepository(db_session),
        ).discover_group_members("cerberus", [server.id])

        assert adapter.calls[0]["command"] == "getent group cerberus; getent passwd"
        assert membership.hosts[0].primary_members == ["cerberus"]
        assert membership.hosts[0].supplementary_members == ["deploy"]
        assert membership.hosts[0].members == ["cerberus", "deploy"]


@pytest.mark.asyncio
async def test_linux_group_update_can_rename_and_replicate(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(**server_payload(hostname="group-identity-01", ip_address="10.4.0.14"))
        )
        adapter = FakeSshAdapter()
        service = LinuxGroupService(
            repository=LinuxGroupRepository(db_session),
            replication_service=IdentityReplicationService(
                job_service=JobService(
                    job_repository=JobRepository(db_session),
                    server_repository=ServerRepository(db_session),
                    ssh_adapter=adapter,
                ),
                execution_repository=IdentityExecutionRepository(db_session),
            ),
        )

        created = await service.create_group(LinuxGroupCreate(name="deploy", target_server_ids=[]))
        updated = await service.update_group(
            created.item.id,
            LinuxGroupUpdate(name="release", description="Release operators", target_server_ids=[server.id]),
        )

        assert updated.item.name == "release"
        assert updated.replication.success_count == 1
        assert "groupmod -n release deploy" in adapter.calls[0]["command"]


@pytest.mark.asyncio
async def test_linux_user_group_update_only_runs_group_changes(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(**server_payload(hostname="user-group-update-identity-01", ip_address="10.4.0.18"))
        )
        adapter = FakeSshAdapter()
        service = LinuxUserService(
            repository=LinuxUserRepository(db_session),
            replication_service=IdentityReplicationService(
                job_service=JobService(
                    job_repository=JobRepository(db_session),
                    server_repository=ServerRepository(db_session),
                    ssh_adapter=adapter,
                ),
                execution_repository=IdentityExecutionRepository(db_session),
            ),
        )

        created = await service.create_user(
            LinuxUserCreate(username="deploy", sudo_enabled=True, target_server_ids=[])
        )
        await service.update_user(
            created.item.id,
            LinuxUserUpdate(sudo_enabled=True, supplementary_groups=["docker"], target_server_ids=[server.id]),
        )

        command = adapter.calls[0]["command"]
        assert "usermod -aG docker deploy" in command
        assert "usermod -s" not in command
        assert "sudoers.d" not in command
        assert "visudo" not in command
        assert "chpasswd" not in command
        assert "passwd -l" not in command
        assert "passwd -u" not in command


@pytest.mark.asyncio
async def test_linux_user_replication_uses_selected_sudo_credential(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(**server_payload(hostname="sudo-credential-identity-01", ip_address="10.4.0.19"))
        )
        adapter = FakeSshAdapter()
        service = LinuxUserService(
            repository=LinuxUserRepository(db_session),
            replication_service=IdentityReplicationService(
                job_service=JobService(
                    job_repository=JobRepository(db_session),
                    server_repository=ServerRepository(db_session),
                    ssh_adapter=adapter,
                    credential_service=FakeCredentialService(),
                ),
                execution_repository=IdentityExecutionRepository(db_session),
            ),
        )

        created = await service.create_user(
            LinuxUserCreate(username="deploy", sudo_enabled=True, target_server_ids=[])
        )
        await service.replicate_user(
            created.item.id,
            ReplicationRequest(target_server_ids=[server.id], credential_ref="sudo-password"),
        )

        assert "sudo() { command sudo -S" in adapter.calls[0]["command"]
        assert adapter.calls[0]["input_data"]
