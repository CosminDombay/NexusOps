from typing import Any

import pytest

from backend.app.adapters.proxmox.base import ProxmoxAdapter
from backend.app.adapters.ssh import SshAdapter, SshExecutionResult
from backend.app.common.constants import (
    InventoryLifecycleState,
    InventorySyncStatus,
    ServerEnvironment,
    ServerSshAuthMethod,
    ServerStatus,
)
from backend.app.modules.inventory.models import Server
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.identity.repository import (
    IdentityExecutionRepository,
    LinuxGroupRepository,
)
from backend.app.modules.identity.schemas import LinuxGroupCreate
from backend.app.modules.identity.service import IdentityReplicationService, LinuxGroupService
from backend.app.modules.deployments.repository import (
    DeploymentRepository,
    DeploymentRevisionRepository,
    DeploymentTargetRepository,
)
from backend.app.modules.deployments.schemas import DeploymentCreate
from backend.app.modules.deployments.service import DockerComposeDeploymentService
from backend.app.modules.jobs.repository import JobRepository
from backend.app.modules.jobs.service import JobService
from backend.app.modules.jobs.models import JobStatus
from backend.app.modules.packages.repository import PackageDefinitionRepository
from backend.app.modules.profiles.repository import InfrastructureProfileRepository
from backend.app.modules.profiles.schemas import InfrastructureProfileCreate
from backend.app.modules.profiles.service import ProfileService
from backend.app.modules.provisioning.repository import (
    ProvisioningBlueprintRepository,
    ProvisioningBootstrapTemplateRepository,
    ProvisioningBatchRepository,
    ProvisioningRequestRepository,
)
from backend.app.modules.provisioning.models import ProvisioningRequest, ProvisioningStatus
from backend.app.modules.provisioning.schemas import (
    ProvisioningBatchCreate,
    ProvisioningBlueprintCreate,
    ProvisioningBootstrapTemplateCreate,
    ProvisioningBootstrapTemplateUpdate,
    ProvisioningCreate,
)
from backend.app.modules.provisioning.service import ProvisioningService


class FakeProxmoxAdapter(ProxmoxAdapter):
    def __init__(self, vms: list[dict[str, Any]] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.vms = vms or []

    @property
    def name(self) -> str:
        return "fake-proxmox"

    async def get_nodes(self) -> list[dict[str, Any]]:
        return []

    async def list_vms(self) -> list[dict[str, Any]]:
        return self.vms

    async def list_vm_templates(self) -> list[dict[str, Any]]:
        return [{"vmid": 9000, "name": "ubuntu-template", "node": "hellgate", "type": "qemu", "template": 1}]

    async def list_lxc_templates(self, *, node: str | None = None) -> list[dict[str, Any]]:
        return [
            {
                "vmid": 9010,
                "name": "debian-12-standard.tar.zst",
                "node": node or "hellgate",
                "type": "lxc",
                "template_ref": "local:vztmpl/debian-12-standard.tar.zst",
                "storage": "local",
            }
        ]

    async def list_storage(self, *, node: str | None = None) -> list[dict[str, Any]]:
        return [{"storage": "local-lvm", "node": node or "hellgate", "type": "lvmthin", "content": "images"}]

    async def get_vm_status(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        return {}

    async def get_cluster_summary(self) -> dict[str, Any]:
        return {}

    async def get_task_status(self, *, node: str, task_id: str) -> dict[str, Any]:
        return {"status": "stopped", "exitstatus": "OK"}

    async def start_vm(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        self.calls.append({"action": "start", "vm_id": vm_id})
        return {"task_id": "UPID:start"}

    async def stop_vm(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        return {}

    async def reboot_vm(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        return {}

    async def shutdown_vm(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        return {}

    async def clone_vm_template(
        self,
        *,
        node: str,
        template_id: int,
        new_vm_id: int,
        name: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append({"action": "clone", "template_id": template_id, "new_vm_id": new_vm_id})
        return {"task_id": "UPID:clone"}

    async def configure_cloud_init(self, **kwargs) -> dict[str, Any]:
        self.calls.append({"action": "config", **kwargs})
        return {"task_id": "UPID:config"}

    async def resize_vm_disk(self, *, node: str, vm_id: int, disk_size_gb: int) -> dict[str, Any]:
        self.calls.append({"action": "resize", "disk_size_gb": disk_size_gb})
        return {"task_id": "UPID:resize"}

    async def add_vm_disk(
        self,
        *,
        node: str,
        vm_id: int,
        disk: str,
        storage: str,
        size_gb: int,
    ) -> dict[str, Any]:
        self.calls.append({"action": "add_disk", "disk": disk, "storage": storage, "size_gb": size_gb})
        return {"task_id": f"UPID:add-{disk}"}

    async def create_lxc_container(self, **kwargs) -> dict[str, Any]:
        self.calls.append({"action": "create_lxc", **kwargs})
        return {"task_id": "UPID:create-lxc"}


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
        self.calls.append(
            {
                "host": host,
                "port": port,
                "command": command,
                "user": user,
                "password": password,
                "input_data": input_data,
            }
        )
        return SshExecutionResult(exit_code=0, stdout="ok\n", stderr="")

    async def upload_file(self, host: str, local_path: str, remote_path: str, user: str) -> None:
        raise NotImplementedError


class BootstrapReadinessFailingSshAdapter(FakeSshAdapter):
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
        self.calls.append(
            {
                "host": host,
                "port": port,
                "command": command,
                "user": user,
                "password": password,
                "input_data": input_data,
            }
        )
        if "cloud-init status --wait" in command:
            return SshExecutionResult(
                exit_code=124,
                stdout="",
                stderr="Timed out waiting for apt lock /var/lib/apt/lists/lock",
            )
        return SshExecutionResult(exit_code=0, stdout="ok\n", stderr="")


def payload(**overrides):
    data = {
        "vm_name": "test-vm",
        "target_node": "hellgate",
        "template_id": 9000,
        "new_vm_id": 150,
        "cpu_cores": 2,
        "memory_mb": 2048,
        "disk_gb": 32,
        "network_bridge": "vmbr0",
        "environment": "lab",
        "tags": ["test"],
        "cloud_init_hostname": "test-vm",
        "cloud_init_username": "ubuntu",
        "cloud_init_password": "secret",
        "static_ip_cidr": "10.3.0.50/24",
        "gateway": "10.3.0.1",
        "dns_servers": ["1.1.1.1"],
    }
    data.update(overrides)
    return data


def service(
    db_session,
    proxmox: FakeProxmoxAdapter | None = None,
    ssh: FakeSshAdapter | None = None,
) -> ProvisioningService:
    return ProvisioningService(
        repository=ProvisioningRequestRepository(db_session),
        blueprint_repository=ProvisioningBlueprintRepository(db_session),
        bootstrap_template_repository=ProvisioningBootstrapTemplateRepository(db_session),
        batch_repository=ProvisioningBatchRepository(db_session),
        server_repository=ServerRepository(db_session),
        job_repository=JobRepository(db_session),
        package_repository=PackageDefinitionRepository(db_session),
        profile_repository=InfrastructureProfileRepository(db_session),
        proxmox_adapter=proxmox or FakeProxmoxAdapter(),
        ssh_adapter=ssh or FakeSshAdapter(),
    )


@pytest.mark.asyncio
async def test_provisioning_lists_templates(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        templates = await service(db_session).list_templates()

        assert templates[0].template_id == 9000
        assert any(template.type == "lxc" and template.template_ref for template in templates)


@pytest.mark.asyncio
async def test_provisioning_lists_storage(client) -> None:
    from backend.app.modules.proxmox.service import ProxmoxService

    storage = await ProxmoxService(FakeProxmoxAdapter()).list_storage("hellgate")

    assert storage[0].storage == "local-lvm"
    assert storage[0].content == ["images"]


@pytest.mark.asyncio
async def test_provisioning_bootstrap_template_crud(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        provisioning_service = service(db_session)
        created = await provisioning_service.create_bootstrap_template(
            ProvisioningBootstrapTemplateCreate(
                name="Docker App Bootstrap",
                description="Install Docker and deploy the app.",
                bootstrap_items=[
                    {"kind": "package", "reference_id": "docker-engine"},
                    {"kind": "deployment", "reference_id": "00000000-0000-0000-0000-000000000001"},
                ],
            )
        )

        assert created.name == "Docker App Bootstrap"
        assert [item.kind for item in created.bootstrap_items] == ["package", "deployment"]

        listed = await provisioning_service.list_bootstrap_templates()
        assert [template.id for template in listed] == [created.id]

        updated = await provisioning_service.update_bootstrap_template(
            created.id,
            ProvisioningBootstrapTemplateUpdate(
                name="Base Docker Bootstrap",
                bootstrap_items=[{"kind": "profile", "reference_id": "base-linux-server"}],
            ),
        )
        assert updated.name == "Base Docker Bootstrap"
        assert updated.bootstrap_items[0].reference_id == "base-linux-server"

        await provisioning_service.delete_bootstrap_template(created.id)
        assert await provisioning_service.list_bootstrap_templates() == []


@pytest.mark.asyncio
async def test_provisioning_creates_vm_and_inventory_record(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        proxmox = FakeProxmoxAdapter()
        result = await service(db_session, proxmox).provision(ProvisioningCreate(**payload()))

        assert result.status == "completed"
        assert result.server_id is not None
        assert "UPID:clone" in result.proxmox_task_ids
        assert proxmox.calls[0]["action"] == "clone"

        servers = await ServerRepository(db_session).list(search="10.3.0.50")
        assert len(servers) == 1
        assert servers[0].provider == "proxmox"
        assert servers[0].source_type == "proxmox"
        assert servers[0].sync_status == InventorySyncStatus.SYNCED
        assert servers[0].sync_state == InventorySyncStatus.SYNCED


@pytest.mark.asyncio
async def test_provisioning_runs_bootstrap_profile_after_inventory_registration(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        proxmox = FakeProxmoxAdapter()
        ssh = FakeSshAdapter()
        result = await service(db_session, proxmox, ssh).provision(
            ProvisioningCreate(
                **payload(
                    vm_name="profile-bootstrap-vm",
                    cloud_init_hostname="profile-bootstrap-vm",
                    new_vm_id=151,
                    static_ip_cidr="10.3.0.51/24",
                    bootstrap_profile_ids=["docker-host"],
                )
            )
        )

        assert result.status == "completed"
        assert result.server_id is not None
        assert len(result.bootstrap_job_ids) == 3
        assert len(result.bootstrap_jobs) == 3
        assert [job.operation_type for job in result.bootstrap_jobs] == [
            "profile:docker-host:install-docker",
            "profile:docker-host:docker-status",
            "profile:docker-host:check-docker-containers",
        ]
        assert all(job.status == JobStatus.SUCCESS for job in result.bootstrap_jobs)

        servers = await ServerRepository(db_session).list(search="10.3.0.51")
        assert len(servers) == 1
        assert servers[0].id == result.server_id
        assert servers[0].lifecycle_state == InventoryLifecycleState.PROVISIONED

        jobs = await JobRepository(db_session).list_for_target(result.server_id)
        assert [job.operation_type for job in reversed(jobs)] == [
            "profile:docker-host:install-docker",
            "profile:docker-host:docker-status",
            "profile:docker-host:check-docker-containers",
        ]
        assert all(str(job.id) in result.bootstrap_job_ids for job in jobs)

        commands = "\n".join(call["command"] for call in ssh.calls)
        assert "get.docker.com" in commands
        assert "systemctl status docker --no-pager" in commands
        assert "docker ps" in commands

        readiness_index = next(
            index for index, call in enumerate(ssh.calls) if "cloud-init status --wait" in call["command"]
        )
        docker_install_index = next(index for index, call in enumerate(ssh.calls) if "get.docker.com" in call["command"])
        assert readiness_index < docker_install_index

        assert servers[0].provider_metadata["bootstrap_readiness_required"] is True
        assert servers[0].provider_metadata["bootstrap_ready"] is True
        assert servers[0].provider_metadata["bootstrap_error"] is None


@pytest.mark.asyncio
async def test_provisioning_stops_bootstrap_when_bootstrap_readiness_times_out(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        ssh = BootstrapReadinessFailingSshAdapter()
        result = await service(db_session, FakeProxmoxAdapter(), ssh).provision(
            ProvisioningCreate(
                **payload(
                    vm_name="bootstrap-not-ready-vm",
                    cloud_init_hostname="bootstrap-not-ready-vm",
                    new_vm_id=153,
                    static_ip_cidr="10.3.0.53/24",
                    bootstrap_package_ids=["docker-engine"],
                )
            )
        )

        assert result.status == "failed"
        assert "Timed out waiting for apt lock" in (result.error_message or "")
        assert result.server_id is not None
        assert result.bootstrap_job_ids == []

        servers = await ServerRepository(db_session).list(search="10.3.0.53")
        assert len(servers) == 1
        assert servers[0].provider_metadata["bootstrap_readiness_required"] is True
        assert servers[0].provider_metadata["bootstrap_ready"] is False
        assert "Timed out waiting for apt lock" in servers[0].provider_metadata["bootstrap_error"]

        commands = "\n".join(call["command"] for call in ssh.calls)
        assert "cloud-init status --wait" in commands
        assert "get.docker.com" not in commands


@pytest.mark.asyncio
async def test_provisioning_bootstrap_profile_can_apply_identity_group_steps(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        ssh = FakeSshAdapter()
        job_service = JobService(
            job_repository=JobRepository(db_session),
            server_repository=ServerRepository(db_session),
            ssh_adapter=ssh,
        )
        identity_replication = IdentityReplicationService(
            job_service=job_service,
            execution_repository=IdentityExecutionRepository(db_session),
        )
        group_service = LinuxGroupService(
            repository=LinuxGroupRepository(db_session),
            replication_service=identity_replication,
        )
        group = await group_service.create_group(
            LinuxGroupCreate(name="infra", members=["cerberus"], target_server_ids=[])
        )
        await ProfileService(
            job_service=job_service,
            repository=InfrastructureProfileRepository(db_session),
        ).create_profile(
            InfrastructureProfileCreate(
                id="identity-bootstrap-profile",
                name="Identity Bootstrap Profile",
                category="Identity",
                description="Applies Linux identity records during provisioning bootstrap.",
                tags=["identity"],
                steps=[
                    {
                        "kind": "identity_group",
                        "reference_id": str(group.item.id),
                        "name": "Apply infra group",
                    }
                ],
            )
        )

        result = await service(db_session, FakeProxmoxAdapter(), ssh).provision(
            ProvisioningCreate(
                **payload(
                    vm_name="identity-bootstrap-vm",
                    cloud_init_hostname="identity-bootstrap-vm",
                    new_vm_id=154,
                    static_ip_cidr="10.3.0.54/24",
                    bootstrap_profile_ids=["identity-bootstrap-profile"],
                )
            )
        )

        assert result.status == "completed"
        assert len(result.bootstrap_job_ids) == 1
        assert result.bootstrap_jobs[0].operation_type == "identity:group:infra:replicate"

        commands = "\n".join(call["command"] for call in ssh.calls)
        assert "cloud-init status --wait" in commands
        assert "groupadd infra" in commands
        assert "usermod -aG infra cerberus" in commands


@pytest.mark.asyncio
async def test_provisioning_runs_ordered_bootstrap_items_with_deployment(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        ssh = FakeSshAdapter()
        server_repository = ServerRepository(db_session)
        job_service = JobService(
            job_repository=JobRepository(db_session),
            server_repository=server_repository,
            ssh_adapter=ssh,
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
                name="provisioned-web",
                compose_content="services:\n  web:\n    image: nginx:alpine\n",
            )
        )

        result = await service(db_session, FakeProxmoxAdapter(), ssh).provision(
            ProvisioningCreate(
                **payload(
                    vm_name="ordered-bootstrap-vm",
                    cloud_init_hostname="ordered-bootstrap-vm",
                    new_vm_id=152,
                    static_ip_cidr="10.3.0.52/24",
                    bootstrap_items=[
                        {"kind": "package", "reference_id": "docker-engine"},
                        {"kind": "deployment", "reference_id": str(deployment.id)},
                    ],
                )
            )
        )

        assert result.status == "completed"
        assert result.bootstrap_profile_ids == []
        assert result.bootstrap_package_ids == ["docker-engine"]
        assert [item.kind for item in result.bootstrap_items] == ["package", "deployment"]
        assert len(result.bootstrap_job_ids) == 2
        assert [job.operation_type for job in result.bootstrap_jobs] == [
            "package:install:docker-engine",
            f"deployment:{deployment.id}:deploy",
        ]

        jobs = await JobRepository(db_session).list_for_target(result.server_id)
        bootstrap_jobs = [job for job in reversed(jobs) if str(job.id) in result.bootstrap_job_ids]
        assert [job.operation_type for job in bootstrap_jobs] == [
            "package:install:docker-engine",
            f"deployment:{deployment.id}:deploy",
        ]
        deployment_targets = await DeploymentTargetRepository(db_session).list_for_deployment(deployment.id)
        assert [target.server_id for target in deployment_targets] == [result.server_id]


@pytest.mark.asyncio
async def test_provisioning_creates_lxc_and_inventory_record(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        proxmox = FakeProxmoxAdapter()
        result = await service(db_session, proxmox).provision(
            ProvisioningCreate(
                **payload(
                    vm_name="test-ct",
                    cloud_init_hostname="test-ct",
                    provisioning_type="lxc",
                    template_id=9010,
                    template_ref="local:vztmpl/debian-12-standard.tar.zst",
                    new_vm_id=250,
                    static_ip_cidr="10.3.0.70/24",
                    cloud_init_username="root",
                )
            )
        )

        assert result.status == "completed"
        assert result.provisioning_type == "lxc"
        assert "UPID:create-lxc" in result.proxmox_task_ids
        assert proxmox.calls[0]["action"] == "create_lxc"
        assert proxmox.calls[1]["action"] == "start"

        servers = await ServerRepository(db_session).list(search="10.3.0.70")
        assert len(servers) == 1
        assert servers[0].node_type.value == "lxc"
        assert servers[0].provider_type == "lxc"
        assert servers[0].provider_metadata["template_ref"] == "local:vztmpl/debian-12-standard.tar.zst"


@pytest.mark.asyncio
async def test_provisioning_batch_creates_children_from_blueprint(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        proxmox = FakeProxmoxAdapter()
        provisioning_service = service(db_session, proxmox)
        blueprint = await provisioning_service.create_blueprint(
            ProvisioningBlueprintCreate(
                name="Docker hosts",
                target_node="hellgate",
                template_id=9000,
                cpu_cores=2,
                memory_mb=2048,
                disk_gb=32,
                network_bridge="vmbr0",
                environment="lab",
                tags=["docker"],
                cloud_init_username="ubuntu",
                gateway="10.3.0.1",
                dns_servers=["1.1.1.1"],
            )
        )

        batch = await provisioning_service.provision_batch(
            ProvisioningBatchCreate(
                name="Lab Docker Batch",
                blueprint_id=blueprint.id,
                count=2,
                vm_name_pattern="lab-docker-{index}",
                hostname_pattern="lab-docker-{index}",
                starting_vm_id=200,
                starting_ip_cidr="10.3.0.60/24",
                cloud_init_password="secret",
            )
        )

        assert batch.status == "completed"
        assert batch.completed_count == 2
        assert batch.failed_count == 0
        assert [request.new_vm_id for request in batch.requests] == [200, 201]
        assert [request.static_ip_cidr for request in batch.requests] == ["10.3.0.60/24", "10.3.0.61/24"]


@pytest.mark.asyncio
async def test_delete_provisioning_request_removes_history_record(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        request = ProvisioningRequest(
            vm_name="failed-vm",
            target_node="hellgate",
            template_id=9000,
            new_vm_id=188,
            cpu_cores=2,
            memory_mb=2048,
            disk_gb=32,
            additional_disks=[],
            network_bridge="vmbr0",
            environment="lab",
            tags=["test"],
            description=None,
            start_on_boot=False,
            cloud_init_username="ubuntu",
            cloud_init_password=None,
            ssh_public_key=None,
            static_ip_cidr="10.3.0.88/24",
            gateway="10.3.0.1",
            dns_servers=["1.1.1.1"],
            status=ProvisioningStatus.FAILED,
            error_message="test failure",
            proxmox_task_ids=[],
            bootstrap_profile_ids=[],
            bootstrap_package_ids=[],
            bootstrap_job_ids=[],
        )
        db_session.add(request)
        await db_session.commit()
        await db_session.refresh(request)
        request_id = request.id

    response = client.delete(f"/api/v1/vms/{request_id}")

    assert response.status_code == 204
    assert client.get("/api/v1/vms").json() == []
    async for db_session in session():
        assert await ProvisioningRequestRepository(db_session).get_by_id(request_id, include_deleted=True) is None


@pytest.mark.asyncio
async def test_sanitize_stale_provisioning_requests_purges_failed_orphan_history(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        stale = ProvisioningRequest(
            vm_name="stale-test",
            target_node="hellgate",
            template_id=9000,
            new_vm_id=210,
            cpu_cores=2,
            memory_mb=2048,
            disk_gb=32,
            additional_disks=[],
            network_bridge="vmbr0",
            environment="lab",
            tags=["test"],
            description=None,
            start_on_boot=False,
            cloud_init_username="ubuntu",
            cloud_init_password=None,
            ssh_public_key=None,
            static_ip_cidr="192.168.50.88/24",
            gateway="192.168.50.1",
            dns_servers=["1.1.1.1"],
            status=ProvisioningStatus.FAILED,
            error_message="Requested static IP or hostname already exists in inventory",
            proxmox_task_ids=[],
            bootstrap_profile_ids=[],
            bootstrap_package_ids=[],
            bootstrap_job_ids=[],
        )
        db_session.add(stale)
        await db_session.commit()
        await db_session.refresh(stale)
        stale_id = stale.id

        result = await service(db_session).sanitize_stale_requests()

        assert result.deleted_count == 1
        assert result.deleted == ["stale-test (hellgate/qemu:210)"]
        assert await ProvisioningRequestRepository(db_session).get_by_id(stale_id, include_deleted=True) is None


@pytest.mark.asyncio
async def test_sanitize_stale_provisioning_requests_skips_existing_inventory_host(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = Server(
            hostname="stale-test",
            ip_address="192.168.50.88",
            operating_system="Ubuntu",
            vmid="210",
            environment=ServerEnvironment.LAB,
            tags=["test"],
            ssh_port=22,
            ssh_username="ubuntu",
            ssh_auth_method=ServerSshAuthMethod.KEY,
            status=ServerStatus.UNKNOWN,
            provider="proxmox",
            external_id="210",
        )
        request = ProvisioningRequest(
            vm_name="stale-test",
            target_node="hellgate",
            template_id=9000,
            new_vm_id=210,
            cpu_cores=2,
            memory_mb=2048,
            disk_gb=32,
            additional_disks=[],
            network_bridge="vmbr0",
            environment="lab",
            tags=["test"],
            description=None,
            start_on_boot=False,
            cloud_init_username="ubuntu",
            cloud_init_password=None,
            ssh_public_key=None,
            static_ip_cidr="192.168.50.88/24",
            gateway="192.168.50.1",
            dns_servers=["1.1.1.1"],
            status=ProvisioningStatus.FAILED,
            error_message="failed after inventory registration",
            proxmox_task_ids=[],
            bootstrap_profile_ids=[],
            bootstrap_package_ids=[],
            bootstrap_job_ids=[],
        )
        db_session.add_all([server, request])
        await db_session.commit()
        await db_session.refresh(request)

        result = await service(db_session).sanitize_stale_requests()

        assert result.deleted_count == 0
        assert result.skipped == ["stale-test: inventory host still references VMID"]
        assert await ProvisioningRequestRepository(db_session).get_by_id(request.id) is not None


@pytest.mark.asyncio
async def test_provisioning_restores_archived_inventory_record_for_reused_ip(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    proxmox = FakeProxmoxAdapter()
    async for db_session in session():
        archived = Server(
            hostname="old-vm",
            ip_address="10.3.0.50",
            operating_system="old Linux",
            vmid="99",
            environment=ServerEnvironment.LAB,
            tags=["old"],
            ssh_port=22,
            ssh_username="ubuntu",
            ssh_auth_method=ServerSshAuthMethod.PASSWORD,
            ssh_password="old",
            status=ServerStatus.OFFLINE,
            provider="proxmox",
            external_id="99",
            source="provisioned",
            managed=False,
            lifecycle_state=InventoryLifecycleState.ARCHIVED,
            sync_status=InventorySyncStatus.ARCHIVED,
            provider_node="hellgate",
            provider_type="qemu",
            provider_metadata={},
        )
        db_session.add(archived)
        await db_session.commit()
        await db_session.refresh(archived)
        archived_id = archived.id

        result = await service(db_session, proxmox).provision(
            ProvisioningCreate(**payload(vm_name="new-vm", cloud_init_hostname="new-vm"))
        )
        restored = await ServerRepository(db_session).get_by_id(archived_id)

        assert result.status == "completed"
        assert str(result.server_id) == str(archived_id)
        assert restored is not None
        assert restored.hostname == "new-vm"
        assert restored.ip_address == "10.3.0.50"
        assert restored.lifecycle_state == InventoryLifecycleState.PROVISIONED
        assert restored.managed is True
        assert restored.sync_state == InventorySyncStatus.SYNCED
