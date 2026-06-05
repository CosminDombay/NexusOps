from typing import Any

import pytest

from backend.app.adapters.ssh import SshAdapter, SshExecutionResult
from backend.app.modules.credentials.schemas import ResolvedCredential
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.schemas import ServerCreate
from backend.app.modules.inventory.service import InventoryService
from backend.app.modules.deployments.repository import (
    DeploymentRepository,
    DeploymentRevisionRepository,
    DeploymentTargetRepository,
)
from backend.app.modules.deployments.schemas import DeploymentCreate
from backend.app.modules.deployments.service import DockerComposeDeploymentService
from backend.app.modules.deployments.runtime import validate_compose_content
from backend.app.modules.jobs.repository import JobRepository
from backend.app.modules.jobs.service import JobService
from backend.app.modules.packages.service import PackageAutomationService
from backend.app.modules.packages.schemas import PackageExecuteRequest
from backend.app.modules.profiles.schemas import ProfileApplyRequest
from backend.app.modules.profiles.schemas import InfrastructureProfileCreate
from backend.app.modules.profiles.repository import InfrastructureProfileRepository
from backend.app.modules.profiles.service import ProfileService
from backend.app.modules.workflows.models import WorkflowStatus, WorkflowStepStatus, WorkflowType
from backend.app.modules.workflows.repository import WorkflowRunRepository, WorkflowStepRepository
from backend.app.modules.workflows.service import WorkflowService


class FakeSshAdapter(SshAdapter):
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.inspect_stdout = '{"Name":"demo-web-1","State":{"Status":"running","StartedAt":"2026-05-24T10:00:00Z"},"Config":{"Labels":{"com.docker.compose.service":"web"}},"RestartCount":0}\n'

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
        if "docker inspect" in command:
            return SshExecutionResult(
                exit_code=0,
                stdout=self.inspect_stdout,
                stderr="",
            )
        return SshExecutionResult(exit_code=0, stdout="ok\n", stderr="")

    async def upload_file(self, host: str, local_path: str, remote_path: str, user: str) -> None:
        raise NotImplementedError


class FakeCredentialService:
    async def resolve_credential(self, credential_id_or_name):
        return ResolvedCredential(
            id="11111111-1111-1111-1111-111111111111",
            name=str(credential_id_or_name),
            credential_type="ssh_password",
            username=None,
            secret="deploy-sudo-secret",
        )


def server_payload(**overrides):
    payload = {
        "hostname": "profile-target-01",
        "ip_address": "10.2.0.10",
        "operating_system": "Ubuntu 24.04 LTS",
        "environment": "lab",
        "provider": "manual",
        "ssh_port": 22,
        "ssh_username": "ubuntu",
    }
    payload.update(overrides)
    return payload


def test_compose_validation_reports_invalid_compose() -> None:
    result = validate_compose_content("version: '3'\n")

    assert result.valid is False
    assert "Compose YAML must define a top-level services section." in result.errors


def test_compose_validation_warns_for_service_without_image_or_build() -> None:
    result = validate_compose_content("services:\n  web:\n    ports:\n      - '8080:80'\n")

    assert result.valid is True
    assert result.services == ["web"]
    assert result.warnings == ["Service web has no image or build directive."]


@pytest.mark.asyncio
async def test_package_service_lists_definitions() -> None:
    packages = await PackageAutomationService().list_definitions()

    assert any(package.id == "docker-engine" for package in packages)
    assert any(package.id == "fail2ban" for package in packages)


@pytest.mark.asyncio
async def test_package_service_uses_execution_credential_for_sudo_jobs(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(**server_payload(hostname="package-sudo-01", ip_address="10.2.0.16"))
        )
        adapter = FakeSshAdapter()
        server_repository = ServerRepository(db_session)
        service = PackageAutomationService(
            job_service=JobService(
                job_repository=JobRepository(db_session),
                server_repository=server_repository,
                ssh_adapter=adapter,
                credential_service=FakeCredentialService(),
            ),
            credential_service=FakeCredentialService(),
        )

        await service.execute_definition(
            "docker-engine",
            PackageExecuteRequest(
                target_server_id=server.id,
                execution_credential_ref="package-sudo-password",
            ),
        )

        assert adapter.calls[0]["password"] == "deploy-sudo-secret"
        assert adapter.calls[0]["input_data"] == "deploy-sudo-secret\n"
        assert "NEXUSOPS_ASKPASS=$(mktemp)" in adapter.calls[0]["command"]


@pytest.mark.asyncio
async def test_profile_service_lists_templates(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        service = ProfileService(
            job_service=JobService(
                job_repository=JobRepository(db_session),
                server_repository=ServerRepository(db_session),
                ssh_adapter=FakeSshAdapter(),
            )
        )

        profiles = await service.list_profiles()

        assert any(profile.id == "docker-host" for profile in profiles)
        assert any(profile.id == "base-linux-server" for profile in profiles)


@pytest.mark.asyncio
async def test_profile_apply_generates_sequential_jobs(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(**server_payload())
        )
        adapter = FakeSshAdapter()
        service = ProfileService(
            job_service=JobService(
                job_repository=JobRepository(db_session),
                server_repository=ServerRepository(db_session),
                ssh_adapter=adapter,
            )
        )

        result = await service.apply_profile(
            "docker-host",
            ProfileApplyRequest(target_server_id=server.id),
        )

        assert result.status == "success"
        assert len(result.jobs) == 3
        assert result.jobs[0].operation_type == "profile:docker-host:install-docker"
        assert "get.docker.com" in adapter.calls[0]["command"]
        assert adapter.calls[1]["command"] == "systemctl status docker --no-pager"


@pytest.mark.asyncio
async def test_profile_apply_records_workflow_trace_when_available(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(**server_payload(hostname="profile-workflow-01", ip_address="10.2.0.14"))
        )
        adapter = FakeSshAdapter()
        server_repository = ServerRepository(db_session)
        workflow_service = WorkflowService(
            workflow_repository=WorkflowRunRepository(db_session),
            step_repository=WorkflowStepRepository(db_session),
            server_repository=server_repository,
        )
        service = ProfileService(
            job_service=JobService(
                job_repository=JobRepository(db_session),
                server_repository=server_repository,
                ssh_adapter=adapter,
            ),
            workflow_service=workflow_service,
        )

        result = await service.apply_profile(
            "base-linux-server",
            ProfileApplyRequest(target_server_id=server.id),
        )

        workflows = await workflow_service.list_workflows(target_server_id=server.id)

        assert result.status == "success"
        assert len(workflows) == 1
        assert workflows[0].workflow_type == WorkflowType.PROFILE_EXECUTION
        assert workflows[0].status == WorkflowStatus.SUCCESS
        assert workflows[0].result_summary["profile_id"] == "base-linux-server"
        assert workflows[0].result_summary["job_count"] == len(result.jobs)
        assert workflows[0].linked_job_ids == sorted(str(job.id) for job in result.jobs)
        assert workflows[0].activity_timeline
        assert any(activity.job_ids for activity in workflows[0].activity_timeline)
        assert all(step.status == WorkflowStepStatus.SUCCESS for step in workflows[0].steps)
        assert all(step.metadata_json["target_server_id"] == str(server.id) for step in workflows[0].steps)


@pytest.mark.asyncio
async def test_profile_apply_runs_deployment_step(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(**server_payload(hostname="deploy-profile-01", ip_address="10.2.0.11"))
        )
        adapter = FakeSshAdapter()
        server_repository = ServerRepository(db_session)
        job_service = JobService(
            job_repository=JobRepository(db_session),
            server_repository=server_repository,
            ssh_adapter=adapter,
        )
        deployment_service = DockerComposeDeploymentService(
            repository=DeploymentRepository(db_session),
            target_repository=DeploymentTargetRepository(db_session),
            revision_repository=DeploymentRevisionRepository(db_session),
            server_repository=server_repository,
            job_service=job_service,
        )
        deployment = await deployment_service.create_deployment(
            DeploymentCreate(
                name="profile-web",
                target_server_id=server.id,
                compose_content="services:\n  web:\n    image: nginx:alpine\n",
            )
        )
        profile_service = ProfileService(
            job_service=job_service,
            repository=InfrastructureProfileRepository(db_session),
            deployment_service=deployment_service,
        )
        profile = await profile_service.create_profile(
            InfrastructureProfileCreate(
                id="deploy-profile",
                name="Deploy Profile",
                category="Custom",
                description="Runs a deployment.",
                tags=[],
                steps=[
                    {
                        "kind": "deployment",
                        "reference_id": str(deployment.id),
                        "name": "Deploy web",
                    }
                ],
            )
        )

        result = await profile_service.apply_profile(
            profile.id,
            ProfileApplyRequest(target_server_id=server.id),
        )

        assert result.status == "success"
        assert len(result.jobs) == 1
        assert result.jobs[0].operation_type == f"deployment:{deployment.id}:deploy"
        command = adapter.calls[0]["command"]
        assert "cat > docker-compose.yaml <<'NEXUSOPS_COMPOSE_EOF'" in command
        assert "\nNEXUSOPS_COMPOSE_EOF\ncat > .env <<'NEXUSOPS_ENV_EOF'" in command
        assert "nexusops_docker compose -f docker-compose.yaml --env-file .env up -d" in command
        assert "sudo docker \"$@\"" in command


@pytest.mark.asyncio
async def test_deployment_service_deletes_record_with_history(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(**server_payload(hostname="delete-deploy-01", ip_address="10.2.0.12"))
        )
        adapter = FakeSshAdapter()
        server_repository = ServerRepository(db_session)
        service = DockerComposeDeploymentService(
            repository=DeploymentRepository(db_session),
            target_repository=DeploymentTargetRepository(db_session),
            revision_repository=DeploymentRevisionRepository(db_session),
            server_repository=server_repository,
            job_service=JobService(
                job_repository=JobRepository(db_session),
                server_repository=server_repository,
                ssh_adapter=adapter,
            ),
        )
        deployment = await service.create_deployment(
            DeploymentCreate(
                name="delete-me",
                target_server_id=server.id,
                compose_content="services:\n  web:\n    image: nginx:alpine\n",
            )
        )
        await service.deploy(deployment.id)

        await service.delete_deployment(deployment.id)

        assert await service.repository.get_by_id(deployment.id) is None
        assert await service.target_repository.get_for_deployment(deployment.id) is None
        assert await service.revision_repository.list_for_deployment(deployment.id) == []


@pytest.mark.asyncio
async def test_deployment_service_updates_record_and_marks_draft(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(**server_payload(hostname="update-deploy-01", ip_address="10.2.0.13"))
        )
        next_server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(**server_payload(hostname="update-deploy-02", ip_address="10.2.0.14"))
        )
        adapter = FakeSshAdapter()
        server_repository = ServerRepository(db_session)
        service = DockerComposeDeploymentService(
            repository=DeploymentRepository(db_session),
            target_repository=DeploymentTargetRepository(db_session),
            revision_repository=DeploymentRevisionRepository(db_session),
            server_repository=server_repository,
            job_service=JobService(
                job_repository=JobRepository(db_session),
                server_repository=server_repository,
                ssh_adapter=adapter,
            ),
        )
        deployment = await service.create_deployment(
            DeploymentCreate(
                name="update-me",
                target_server_id=server.id,
                compose_content="services:\n  web:\n    image: nginx:alpine\n",
            )
        )
        deployed = await service.deploy(deployment.id)
        assert deployed.deployment.status == "running"

        updated = await service.update_deployment(
            deployment.id,
            DeploymentCreate(
                name="updated-deployment",
                target_server_id=next_server.id,
                compose_content="services:\n  web:\n    image: caddy:alpine\n",
                env_content="APP_ENV=lab",
                remote_path="/home/ubuntu/nexusops/deployments",
                execution_credential_ref="deploy-sudo-password",
            ),
        )

        assert updated.name == "updated-deployment"
        assert updated.status == "draft"
        assert updated.target_server_id == next_server.id
        assert updated.target_server_ids == [next_server.id]
        assert "image: caddy:alpine" in updated.compose_content
        assert updated.env_content == "APP_ENV=lab"
        assert updated.execution_credential_ref == "deploy-sudo-password"
        assert updated.remote_path == "/home/ubuntu/nexusops/deployments"


@pytest.mark.asyncio
async def test_deployment_service_uses_execution_credential_for_docker_jobs(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(**server_payload(hostname="deploy-sudo-01", ip_address="10.2.0.15"))
        )
        adapter = FakeSshAdapter()
        server_repository = ServerRepository(db_session)
        service = DockerComposeDeploymentService(
            repository=DeploymentRepository(db_session),
            target_repository=DeploymentTargetRepository(db_session),
            revision_repository=DeploymentRevisionRepository(db_session),
            server_repository=server_repository,
            job_service=JobService(
                job_repository=JobRepository(db_session),
                server_repository=server_repository,
                ssh_adapter=adapter,
                credential_service=FakeCredentialService(),
            ),
        )
        deployment = await service.create_deployment(
            DeploymentCreate(
                name="sudo-deployment",
                target_server_id=server.id,
                compose_content="services:\n  web:\n    image: nginx:alpine\n",
                execution_credential_ref="deploy-sudo-password",
            )
        )

        await service.deploy(deployment.id)

        assert adapter.calls[0]["password"] == "deploy-sudo-secret"
        assert adapter.calls[0]["input_data"] == "deploy-sudo-secret\n"
        assert "NEXUSOPS_ASKPASS=$(mktemp)" in adapter.calls[0]["command"]
        assert "nexusops_ensure_deployment_dir" in adapter.calls[0]["command"]
        assert "sudo mkdir -p \"$deployment_dir\"" in adapter.calls[0]["command"]
        assert "sudo chown \"$(id -u):$(id -g)\" \"$deployment_dir\"" in adapter.calls[0]["command"]
        assert "sudo docker \"$@\"" in adapter.calls[0]["command"]


@pytest.mark.asyncio
async def test_deployment_dry_run_returns_validation_and_redacted_commands(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(**server_payload(hostname="deploy-preview-01", ip_address="10.2.0.17"))
        )
        adapter = FakeSshAdapter()
        server_repository = ServerRepository(db_session)
        service = DockerComposeDeploymentService(
            repository=DeploymentRepository(db_session),
            target_repository=DeploymentTargetRepository(db_session),
            revision_repository=DeploymentRevisionRepository(db_session),
            server_repository=server_repository,
            job_service=JobService(
                job_repository=JobRepository(db_session),
                server_repository=server_repository,
                ssh_adapter=adapter,
            ),
        )
        deployment = await service.create_deployment(
            DeploymentCreate(
                name="preview-deployment",
                target_server_id=server.id,
                compose_content="services:\n  web:\n    image: nginx:alpine\n",
                env_content="APP_ENV=lab",
            )
        )

        preview = await service.dry_run(deployment.id)

        assert preview.validation.valid is True
        assert preview.validation.services == ["web"]
        assert preview.env_keys == ["APP_ENV"]
        assert preview.targets[0].hostname == "deploy-preview-01"
        assert "docker-compose.yaml" in preview.targets[0].redacted_command_preview
        assert "up -d" in preview.targets[0].redacted_command_preview


@pytest.mark.asyncio
async def test_deployment_runtime_refresh_persists_stopped_container_state(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(**server_payload(hostname="runtime-drift-01", ip_address="10.2.0.14"))
        )
        adapter = FakeSshAdapter()
        server_repository = ServerRepository(db_session)
        service = DockerComposeDeploymentService(
            repository=DeploymentRepository(db_session),
            target_repository=DeploymentTargetRepository(db_session),
            revision_repository=DeploymentRevisionRepository(db_session),
            server_repository=server_repository,
            job_service=JobService(
                job_repository=JobRepository(db_session),
                server_repository=server_repository,
                ssh_adapter=adapter,
            ),
        )
        deployment = await service.create_deployment(
            DeploymentCreate(
                name="runtime-drift",
                target_server_id=server.id,
                compose_content="services:\n  web:\n    image: nginx:alpine\n",
            )
        )
        deployed = await service.deploy(deployment.id)
        assert deployed.deployment.runtime_state == "running"

        adapter.inspect_stdout = '{"Name":"demo-web-1","State":{"Status":"exited","StartedAt":"2026-05-24T10:00:00Z"},"Config":{"Labels":{"com.docker.compose.service":"web"}},"RestartCount":0}\n'
        refreshed = await service.refresh_runtime(deployment.id)

        assert refreshed.runtime_state == "stopped"
        assert refreshed.status == "stopped"
        assert refreshed.sync_status == "drifted"
        assert refreshed.targets[0].containers[0].state == "exited"

        inspect_calls = len([call for call in adapter.calls if "docker inspect" in call["command"]])
        listed = await service.list_deployments()
        assert listed[0].runtime_state == "stopped"
        assert len([call for call in adapter.calls if "docker inspect" in call["command"]]) == inspect_calls


def test_deployment_heredoc_marker_changes_when_content_contains_marker() -> None:
    script = DockerComposeDeploymentService._heredoc(
        "docker-compose.yaml",
        "services:\nNEXUSOPS_COMPOSE_EOF\n  app:\n    image: nginx",
        "NEXUSOPS_COMPOSE_EOF",
    )

    first_line, *_, last_line = script.splitlines()

    assert first_line != "cat > docker-compose.yaml <<'NEXUSOPS_COMPOSE_EOF'"
    assert first_line.startswith("cat > docker-compose.yaml <<'NEXUSOPS_COMPOSE_EOF_")
    assert last_line.startswith("NEXUSOPS_COMPOSE_EOF_")


def test_deployment_docker_command_uses_sudo_fallback_wrapper() -> None:
    command = DockerComposeDeploymentService._docker_compose("ps")
    wrapper = DockerComposeDeploymentService._docker_sudo_fallback_function()

    assert command == "nexusops_docker compose -f docker-compose.yaml --env-file .env ps"
    assert "sudo docker \"$@\"" in wrapper
    assert "if sudo docker \"$@\" 2>\"$sudo_err_file\"; then" in wrapper
    assert wrapper.index("if sudo docker") < wrapper.index("cat \"$err_file\" >&2")


def test_deployment_filesystem_command_uses_sudo_fallback_for_protected_paths() -> None:
    wrapper = DockerComposeDeploymentService._deployment_filesystem_function()

    assert "if mkdir -p \"$deployment_dir\" 2>/dev/null; then return 0; fi" in wrapper
    assert "sudo mkdir -p \"$deployment_dir\"" in wrapper
    assert "sudo chown \"$(id -u):$(id -g)\" \"$deployment_dir\"" in wrapper


def test_deployment_heredoc_marker_keeps_changing_until_unique() -> None:
    marker = "NEXUSOPS_COMPOSE_EOF"
    first_script = DockerComposeDeploymentService._heredoc(
        "docker-compose.yaml",
        marker,
        marker,
    )
    generated_marker = first_script.split("<<'", 1)[1].split("'", 1)[0]

    script = DockerComposeDeploymentService._heredoc(
        "docker-compose.yaml",
        f"{marker}\n{generated_marker}",
        marker,
    )

    first_line, *_, last_line = script.splitlines()

    assert generated_marker not in {first_line.split("<<'", 1)[1].split("'", 1)[0], last_line}


def test_profiles_router_lists_profiles(client) -> None:
    response = client.get("/api/v1/profiles")

    assert response.status_code == 200
    assert any(profile["id"] == "monitoring-node" for profile in response.json())


def test_packages_router_lists_packages(client) -> None:
    response = client.get("/api/v1/packages")

    assert response.status_code == 200
    assert any(package["id"] == "tailscale" for package in response.json())
