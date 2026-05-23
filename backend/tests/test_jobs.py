from typing import Any

import pytest

from backend.app.adapters.ssh import SshAdapter, SshConnectionError, SshExecutionResult
from backend.app.modules.inventory.models import Server
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.service import InventoryService
from backend.app.modules.inventory.schemas import ServerCreate
from backend.app.modules.jobs.models import JobStatus
from backend.app.modules.jobs.repository import CustomOperationalActionRepository, JobRepository
from backend.app.modules.jobs.schemas import (
    JobActionExecuteRequest,
    JobBulkExecuteRequest,
    JobExecuteRequest,
    OperationalActionCreate,
)
from backend.app.modules.jobs.service import (
    JobService,
    JobTargetNotFoundError,
    OperationalActionNotFoundError,
)


class FakeSshAdapter(SshAdapter):
    def __init__(self, *, exit_code: int = 0, fail_connect: bool = False) -> None:
        self.exit_code = exit_code
        self.fail_connect = fail_connect
        self.calls: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return "fake-ssh"

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
        self.calls.append(
            {
                "host": host,
                "port": port,
                "command": command,
                "user": user,
                "password": password,
                "private_key_path": private_key_path,
                "private_key": private_key,
                "passphrase": passphrase,
            }
        )
        if self.fail_connect:
            raise SshConnectionError("connection refused")
        return SshExecutionResult(
            exit_code=self.exit_code,
            stdout="linux-host\n",
            stderr="" if self.exit_code == 0 else "command failed\n",
        )

    async def upload_file(self, host: str, local_path: str, remote_path: str, user: str) -> None:
        raise NotImplementedError


def server_payload(**overrides):
    payload = {
        "hostname": "job-target-01",
        "ip_address": "10.1.0.10",
        "operating_system": "Ubuntu 24.04 LTS",
        "vmid": "201",
        "environment": "development",
        "tags": ["jobs"],
        "ssh_port": 2222,
        "ssh_username": "ubuntu",
        "status": "online",
        "provider": "manual",
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_job_service_executes_command_and_persists_success(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(**server_payload())
        )
        adapter = FakeSshAdapter()
        service = JobService(
            job_repository=JobRepository(db_session),
            server_repository=ServerRepository(db_session),
            ssh_adapter=adapter,
        )

        job = await service.execute(
            JobExecuteRequest(target_server_id=server.id, command="hostnamectl")
        )

        assert job.status == JobStatus.SUCCESS
        assert job.stdout == "linux-host\n"
        assert job.exit_code == 0
        assert job.started_at is not None
        assert job.completed_at is not None
        assert job.target_hostname == "job-target-01"
        assert adapter.calls == [
            {
                "host": "10.1.0.10",
                "port": 2222,
                "command": "hostnamectl",
                "user": "ubuntu",
                "password": None,
                "private_key_path": None,
                "private_key": None,
                "passphrase": None,
            }
        ]


@pytest.mark.asyncio
async def test_job_service_uses_password_auth_when_configured(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(
                **server_payload(
                    hostname="password-target-01",
                    ip_address="10.1.0.12",
                    ssh_auth_method="password",
                    ssh_password="secret",
                )
            )
        )
        adapter = FakeSshAdapter()
        service = JobService(
            job_repository=JobRepository(db_session),
            server_repository=ServerRepository(db_session),
            ssh_adapter=adapter,
        )

        await service.execute(JobExecuteRequest(target_server_id=server.id, command="uptime"))

        assert adapter.calls[0]["password"] == "secret"
        assert adapter.calls[0]["private_key_path"] is None


@pytest.mark.asyncio
async def test_job_service_marks_nonzero_exit_as_failed(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(**server_payload(hostname="job-target-02", ip_address="10.1.0.11"))
        )
        service = JobService(
            job_repository=JobRepository(db_session),
            server_repository=ServerRepository(db_session),
            ssh_adapter=FakeSshAdapter(exit_code=1),
        )

        job = await service.execute(JobExecuteRequest(target_server_id=server.id, command="false"))

        assert job.status == JobStatus.FAILED
        assert job.exit_code == 1
        assert job.stderr == "command failed\n"


@pytest.mark.asyncio
async def test_bulk_job_request_dedupes_target_ids(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(**server_payload(hostname="bulk-target-01", ip_address="10.1.0.21"))
        )
        adapter = FakeSshAdapter()
        service = JobService(
            job_repository=JobRepository(db_session),
            server_repository=ServerRepository(db_session),
            ssh_adapter=adapter,
        )

        result = await service.execute_bulk(
            JobBulkExecuteRequest(
                target_server_ids=[server.id, server.id],
                command="uptime",
            )
        )

        assert result.success_count == 1
        assert result.failure_count == 0
        assert len(result.results) == 1
        assert len(adapter.calls) == 1


@pytest.mark.asyncio
async def test_job_service_requires_inventory_target(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        service = JobService(
            job_repository=JobRepository(db_session),
            server_repository=ServerRepository(db_session),
            ssh_adapter=FakeSshAdapter(),
        )

        with pytest.raises(JobTargetNotFoundError):
            await service.execute(
                JobExecuteRequest(
                    target_server_id="00000000-0000-0000-0000-000000000001",
                    command="uptime",
                )
            )


def test_jobs_router_rejects_missing_target(client) -> None:
    response = client.post(
        "/api/v1/jobs/execute",
        json={
            "target_server_id": "00000000-0000-0000-0000-000000000001",
            "command": "uptime",
        },
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_job_service_lists_predefined_actions(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        service = JobService(
            job_repository=JobRepository(db_session),
            server_repository=ServerRepository(db_session),
            ssh_adapter=FakeSshAdapter(),
        )

        actions = await service.list_actions()

        assert any(action.id == "check-uptime" for action in actions)
        assert any(action.id == "restart-docker" and action.destructive for action in actions)


@pytest.mark.asyncio
async def test_job_service_executes_predefined_action_through_jobs(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(
                **server_payload(hostname="action-target-01", ip_address="10.1.0.13")
            )
        )
        adapter = FakeSshAdapter()
        service = JobService(
            job_repository=JobRepository(db_session),
            server_repository=ServerRepository(db_session),
            ssh_adapter=adapter,
        )

        job = await service.execute_action(
            JobActionExecuteRequest(target_server_id=server.id, action_id="check-uptime")
        )

        assert job.operation_type == "action:check-uptime"
        assert job.command == "uptime"
        assert job.status == JobStatus.SUCCESS
        assert adapter.calls[0]["command"] == "uptime"


@pytest.mark.asyncio
async def test_job_service_creates_and_executes_custom_action(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(
                **server_payload(hostname="custom-action-target-01", ip_address="10.1.0.14")
            )
        )
        adapter = FakeSshAdapter()
        service = JobService(
            job_repository=JobRepository(db_session),
            server_repository=ServerRepository(db_session),
            ssh_adapter=adapter,
            action_repository=CustomOperationalActionRepository(db_session),
        )
        action = await service.create_action(
            OperationalActionCreate(
                id="enable-docker-user",
                name="Enable Docker User",
                category="Docker",
                description="Add the SSH user to the docker group.",
                command="sudo usermod -aG docker $USER\nid",
                destructive=True,
            )
        )

        job = await service.execute_action(
            JobActionExecuteRequest(target_server_id=server.id, action_id=action.id)
        )

        assert action.is_builtin is False
        assert job.operation_type == "action:enable-docker-user"
        assert adapter.calls[0]["command"] == "sudo usermod -aG docker $USER\nid"


@pytest.mark.asyncio
async def test_job_service_rejects_unknown_action(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        service = JobService(
            job_repository=JobRepository(db_session),
            server_repository=ServerRepository(db_session),
            ssh_adapter=FakeSshAdapter(),
        )

        with pytest.raises(OperationalActionNotFoundError):
            await service.execute_action(
                JobActionExecuteRequest(
                    target_server_id="00000000-0000-0000-0000-000000000001",
                    action_id="missing-action",
                )
            )


def test_jobs_router_lists_actions(client) -> None:
    response = client.get("/api/v1/jobs/actions")

    assert response.status_code == 200
    actions = response.json()
    assert any(action["id"] == "check-disk-usage" for action in actions)
