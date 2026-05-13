from typing import Any

import pytest

from backend.app.adapters.ssh import SshAdapter, SshExecutionResult
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.schemas import ServerCreate
from backend.app.modules.inventory.service import InventoryService
from backend.app.modules.jobs.repository import JobRepository
from backend.app.modules.jobs.service import JobService
from backend.app.modules.packages.service import PackageAutomationService
from backend.app.modules.profiles.schemas import ProfileApplyRequest
from backend.app.modules.profiles.service import ProfileService


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
    ) -> SshExecutionResult:
        self.calls.append({"host": host, "command": command, "user": user})
        return SshExecutionResult(exit_code=0, stdout="ok\n", stderr="")

    async def upload_file(self, host: str, local_path: str, remote_path: str, user: str) -> None:
        raise NotImplementedError


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


@pytest.mark.asyncio
async def test_package_service_lists_definitions() -> None:
    packages = await PackageAutomationService().list_definitions()

    assert any(package.id == "docker-engine" for package in packages)
    assert any(package.id == "fail2ban" for package in packages)


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


def test_profiles_router_lists_profiles(client) -> None:
    response = client.get("/api/v1/profiles")

    assert response.status_code == 200
    assert any(profile["id"] == "monitoring-node" for profile in response.json())


def test_packages_router_lists_packages(client) -> None:
    response = client.get("/api/v1/packages")

    assert response.status_code == 200
    assert any(package["id"] == "tailscale" for package in response.json())
