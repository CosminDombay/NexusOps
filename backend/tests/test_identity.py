from typing import Any

import pytest

from backend.app.adapters.ssh import SshAdapter, SshExecutionResult
from backend.app.modules.identity.repository import IdentityExecutionRepository, LinuxUserRepository
from backend.app.modules.identity.schemas import LinuxUserCreate, ReplicationRequest
from backend.app.modules.identity.service import IdentityReplicationService, LinuxUserService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.schemas import ServerCreate
from backend.app.modules.inventory.service import InventoryService
from backend.app.modules.jobs.repository import JobRepository
from backend.app.modules.jobs.service import JobService


class FakeSshAdapter(SshAdapter):
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

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
    ) -> SshExecutionResult:
        self.calls.append({"host": host, "command": command, "user": user})
        return SshExecutionResult(exit_code=0, stdout="identity ok\n", stderr="")

    async def upload_file(self, host: str, local_path: str, remote_path: str, user: str) -> None:
        raise NotImplementedError


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


def test_identity_router_lists_users(client) -> None:
    response = client.get("/api/v1/identity/users")

    assert response.status_code == 200
    assert response.json() == []
