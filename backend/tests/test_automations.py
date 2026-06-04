from typing import Any

import pytest

from backend.app.adapters.ssh import SshAdapter, SshExecutionResult
from backend.app.modules.automations.factory import build_automation_service
from backend.app.modules.automations.models import AutomationOperationType, AutomationScheduleType, AutomationTargetMode
from backend.app.modules.automations.schemas import AutomationCreate
from backend.app.modules.credentials.schemas import ResolvedCredential
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.schemas import ServerCreate
from backend.app.modules.inventory.service import InventoryService
from backend.app.modules.jobs.repository import JobRepository
from backend.app.modules.jobs.service import JobService
from backend.app.modules.workflows.models import WorkflowStatus


class FakeSshAdapter(SshAdapter):
    def __init__(self) -> None:
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
        input_data: str | None = None,
    ) -> SshExecutionResult:
        self.calls.append({"host": host, "command": command, "user": user, "password": password, "input_data": input_data})
        return SshExecutionResult(exit_code=0, stdout=f"ran {command}", stderr="")

    async def upload_file(self, host: str, local_path: str, remote_path: str, user: str) -> None:
        raise NotImplementedError


def server_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "hostname": "automation-target-01",
        "ip_address": "10.4.0.10",
        "operating_system": "Ubuntu 24.04",
        "environment": "lab",
        "provider": "manual",
        "ssh_port": 22,
        "ssh_username": "ubuntu",
    }
    payload.update(overrides)
    return payload


class FakeCredentialService:
    async def resolve_credential(self, credential_id_or_name):
        return ResolvedCredential(
            id="22222222-2222-2222-2222-222222222222",
            name=str(credential_id_or_name),
            credential_type="ssh_password",
            username=None,
            secret="automation-sudo-secret",
        )


@pytest.mark.asyncio
async def test_automation_run_creates_workflow_and_steps(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(**server_payload())
        )
        service = build_automation_service(db_session)
        adapter = FakeSshAdapter()
        service.job_service = JobService(
            job_repository=JobRepository(db_session),
            server_repository=ServerRepository(db_session),
            ssh_adapter=adapter,
            credential_service=FakeCredentialService(),
        )
        automation = await service.create_automation(
            AutomationCreate(
                name="Hourly uptime",
                schedule_type=AutomationScheduleType.INTERVAL,
                interval_seconds=3600,
                target_mode=AutomationTargetMode.SINGLE_HOST,
                target_server_ids=[server.id],
                operation_type=AutomationOperationType.ACTION,
                reference_id="check-uptime",
                execution_credential_ref="automation-sudo-password",
            )
        )
        workflow = await service.create_run_workflow(automation.id)

        await service.execute_automation_workflow(automation.id, workflow.id)
        completed = await service.workflow_service.get_workflow(workflow.id)

        assert completed.status == WorkflowStatus.SUCCESS
        assert completed.steps[0].status == "success"
        assert "ran uptime" in completed.steps[0].log_output
        assert adapter.calls[0]["password"] == "automation-sudo-secret"
