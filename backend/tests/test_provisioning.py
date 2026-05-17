from typing import Any

import pytest

from backend.app.adapters.proxmox.base import ProxmoxAdapter
from backend.app.adapters.ssh import SshAdapter, SshExecutionResult
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.jobs.repository import JobRepository
from backend.app.modules.packages.repository import PackageDefinitionRepository
from backend.app.modules.profiles.repository import InfrastructureProfileRepository
from backend.app.modules.provisioning.repository import (
    ProvisioningBlueprintRepository,
    ProvisioningBatchRepository,
    ProvisioningRequestRepository,
)
from backend.app.modules.provisioning.schemas import ProvisioningBatchCreate, ProvisioningBlueprintCreate, ProvisioningCreate
from backend.app.modules.provisioning.service import ProvisioningService


class FakeProxmoxAdapter(ProxmoxAdapter):
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return "fake-proxmox"

    async def get_nodes(self) -> list[dict[str, Any]]:
        return []

    async def list_vms(self) -> list[dict[str, Any]]:
        return []

    async def list_vm_templates(self) -> list[dict[str, Any]]:
        return [{"vmid": 9000, "name": "ubuntu-template", "node": "hellgate", "type": "qemu", "template": 1}]

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


class FakeSshAdapter(SshAdapter):
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
        return SshExecutionResult(exit_code=0, stdout="ok\n", stderr="")

    async def upload_file(self, host: str, local_path: str, remote_path: str, user: str) -> None:
        raise NotImplementedError


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


def service(db_session, proxmox: FakeProxmoxAdapter | None = None) -> ProvisioningService:
    return ProvisioningService(
        repository=ProvisioningRequestRepository(db_session),
        blueprint_repository=ProvisioningBlueprintRepository(db_session),
        batch_repository=ProvisioningBatchRepository(db_session),
        server_repository=ServerRepository(db_session),
        job_repository=JobRepository(db_session),
        package_repository=PackageDefinitionRepository(db_session),
        profile_repository=InfrastructureProfileRepository(db_session),
        proxmox_adapter=proxmox or FakeProxmoxAdapter(),
        ssh_adapter=FakeSshAdapter(),
    )


@pytest.mark.asyncio
async def test_provisioning_lists_templates(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        templates = await service(db_session).list_templates()

        assert templates[0].template_id == 9000


@pytest.mark.asyncio
async def test_provisioning_lists_storage(client) -> None:
    from backend.app.modules.proxmox.service import ProxmoxService

    storage = await ProxmoxService(FakeProxmoxAdapter()).list_storage("hellgate")

    assert storage[0].storage == "local-lvm"
    assert storage[0].content == ["images"]


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
