from typing import Any
from uuid import UUID

import pytest

from backend.app.adapters.proxmox.base import ProxmoxAdapter
from backend.app.common.constants import InventorySyncStatus, ServerEnvironment, ServerSshAuthMethod, ServerStatus
from backend.app.modules.inventory.models import InventoryLifecycleState, ManagedNodeType, ManagementState, Server
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.proxmox.service import ProxmoxService, ProxmoxVmActionNotAllowedError


class FakeProxmoxAdapter(ProxmoxAdapter):
    @property
    def name(self) -> str:
        return "fake-proxmox"

    async def get_nodes(self) -> list[dict[str, Any]]:
        return [
            {
                "node": "pve-01",
                "status": "online",
                "cpu": 0.25,
                "mem": 2_147_483_648,
                "maxmem": 8_589_934_592,
                "uptime": 90_000,
                "ip": "10.0.0.10",
            }
        ]

    async def list_vms(self) -> list[dict[str, Any]]:
        return [
            {
                "vmid": 101,
                "name": "app-01",
                "node": "pve-01",
                "type": "qemu",
                "status": "running",
                "cpu": 0.1,
                "mem": 536_870_912,
                "maxmem": 2_147_483_648,
                "uptime": 3_600,
            },
            {
                "vmid": 102,
                "name": "db-01",
                "node": "pve-01",
                "type": "qemu",
                "status": "stopped",
            },
            {
                "vmid": 201,
                "name": "ct-01",
                "node": "pve-01",
                "type": "lxc",
                "status": "running",
                "ip": "10.0.0.201",
                "mem": 268_435_456,
                "maxmem": 536_870_912,
                "disk": 1_073_741_824,
                "maxdisk": 8_589_934_592,
                "uptime": 900,
            },
        ]

    async def list_vm_templates(self) -> list[dict[str, Any]]:
        return []

    async def get_vm_status(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        return {
            "vmid": vm_id,
            "name": "app-01",
            "node": node,
            "type": vm_type,
            "status": "running",
        }

    async def get_cluster_summary(self) -> dict[str, Any]:
        return {"resources": []}

    async def get_task_status(self, *, node: str, task_id: str) -> dict[str, Any]:
        return {"status": "stopped", "exitstatus": "OK"}

    async def start_vm(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        return {"task_id": f"UPID:{node}:{vm_type}:{vm_id}:start"}

    async def stop_vm(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        return {"task_id": f"UPID:{node}:{vm_type}:{vm_id}:stop"}

    async def reboot_vm(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        return {"task_id": f"UPID:{node}:{vm_type}:{vm_id}:reboot"}

    async def shutdown_vm(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        return {"task_id": f"UPID:{node}:{vm_type}:{vm_id}:shutdown"}

    async def clone_vm_template(
        self,
        *,
        node: str,
        template_id: int,
        new_vm_id: int,
        name: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        return {"task_id": f"UPID:{node}:clone:{template_id}:{new_vm_id}"}

    async def configure_cloud_init(
        self,
        *,
        node: str,
        vm_id: int,
        cpu_cores: int,
        memory_mb: int,
        network_bridge: str,
        username: str,
        password: str | None,
        ssh_public_key: str | None,
        ip_cidr: str,
        gateway: str,
        dns_servers: list[str],
        start_on_boot: bool,
        description: str | None = None,
    ) -> dict[str, Any]:
        return {"task_id": f"UPID:{node}:config:{vm_id}"}

    async def resize_vm_disk(self, *, node: str, vm_id: int, disk_size_gb: int) -> dict[str, Any]:
        return {"task_id": f"UPID:{node}:resize:{vm_id}"}

    async def delete_vm(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        return {"task_id": f"UPID:{node}:{vm_type}:{vm_id}:delete"}


class SecondFakeProxmoxAdapter(FakeProxmoxAdapter):
    async def list_vms(self) -> list[dict[str, Any]]:
        return [
            {
                **item,
                "name": f"b-{item['name']}",
                "ip": f"10.1.0.{item['vmid'] % 255}",
            }
            for item in await super().list_vms()
        ]


@pytest.mark.asyncio
async def test_proxmox_dashboard_normalizes_cluster_state() -> None:
    dashboard = await ProxmoxService(FakeProxmoxAdapter()).get_dashboard()

    assert dashboard.summary.node_count == 1
    assert dashboard.summary.vm_count == 3
    assert dashboard.summary.running_vm_count == 2
    assert dashboard.summary.stopped_vm_count == 1
    assert dashboard.nodes[0].name == "pve-01"
    assert dashboard.nodes[0].vm_count == 2
    assert dashboard.nodes[0].lxc_count == 1
    assert dashboard.vms[0].vm_id == 101


@pytest.mark.asyncio
async def test_proxmox_start_action_resolves_stopped_vm() -> None:
    action = await ProxmoxService(FakeProxmoxAdapter()).start_vm(102)

    assert action.vm_id == 102
    assert action.action == "start"
    assert action.status == "accepted"
    assert action.task_id == "UPID:pve-01:qemu:102:start"


@pytest.mark.asyncio
async def test_proxmox_reboot_requires_running_vm() -> None:
    with pytest.raises(ProxmoxVmActionNotAllowedError):
        await ProxmoxService(FakeProxmoxAdapter()).reboot_vm(102)


@pytest.mark.asyncio
async def test_proxmox_host_sync_imports_hypervisor_inventory(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        result = await ProxmoxService(
            FakeProxmoxAdapter(),
            server_repository=ServerRepository(db_session),
            integration_id="11111111-1111-1111-1111-111111111111",
        ).sync_hosts()

        servers = await ServerRepository(db_session).list_by_provider("proxmox")

        assert result.discovered_count == 1
        assert result.imported_count == 1
        assert result.skipped_count == 0
        assert len(servers) == 1
        assert servers[0].hostname == "pve-01"
        assert servers[0].ip_address == "10.0.0.10"
        assert servers[0].node_type == ManagedNodeType.HYPERVISOR
        assert servers[0].provider_type == "node"
        assert servers[0].provider_metadata["running_vm_count"] == 1


def test_proxmox_global_host_sync_requires_enabled_integration(client) -> None:
    response = client.post("/api/v1/proxmox/hosts/sync")

    assert response.status_code == 503
    assert response.json()["detail"] == "No enabled Proxmox integration is configured"


def test_proxmox_global_guest_sync_requires_enabled_integration(client) -> None:
    response = client.post("/api/v1/proxmox/guests/sync")

    assert response.status_code == 503
    assert response.json()["detail"] == "No enabled Proxmox integration is configured"


@pytest.mark.asyncio
async def test_proxmox_host_sync_adopts_legacy_hostname_record(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        integration_id = UUID("11111111-1111-1111-1111-111111111111")
        repository = ServerRepository(db_session)
        legacy = await repository.create(
            Server(
                hostname="pve-01",
                ip_address="10.0.0.10",
                operating_system="Proxmox VE",
                node_type=ManagedNodeType.HYPERVISOR,
                environment=ServerEnvironment.LAB,
                tags=["legacy"],
                ssh_port=22,
                ssh_username="root",
                ssh_auth_method=ServerSshAuthMethod.KEY,
                status=ServerStatus.ONLINE,
                provider="proxmox",
                external_id="pve-01",
                source="imported",
                managed=True,
                management_state=ManagementState.MANAGED,
                lifecycle_state=InventoryLifecycleState.MANAGED,
                sync_status=InventorySyncStatus.SYNCED,
                sync_state=InventorySyncStatus.SYNCED,
            )
        )

        result = await ProxmoxService(
            FakeProxmoxAdapter(),
            server_repository=repository,
            integration_id=integration_id,
            integration_name="Cluster A",
        ).sync_hosts()

        servers = await repository.list_by_provider("proxmox")

        assert result.imported_count == 0
        assert result.updated_count == 1
        assert len(servers) == 1
        assert servers[0].id == legacy.id
        assert servers[0].integration_id == integration_id
        assert servers[0].external_id == f"{integration_id}:pve-01"
        assert servers[0].provider_metadata["integration_name"] == "Cluster A"


@pytest.mark.asyncio
async def test_proxmox_guest_sync_imports_lxc_inventory(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        result = await ProxmoxService(
            FakeProxmoxAdapter(),
            server_repository=ServerRepository(db_session),
        ).sync_guests()

        servers = await ServerRepository(db_session).list_by_provider("proxmox")
        lxc = next(server for server in servers if server.provider_type == "lxc")

        assert result.discovered_count == 3
        assert result.imported_count == 3
        assert lxc.hostname == "ct-01"
        assert lxc.node_type == ManagedNodeType.LXC
        assert lxc.provider_metadata["operational_readiness"] == "booted"


@pytest.mark.asyncio
async def test_proxmox_guest_sync_adopts_legacy_vmid_record(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        integration_id = UUID("11111111-1111-1111-1111-111111111111")
        repository = ServerRepository(db_session)
        legacy = await repository.create(
            Server(
                hostname="app-01",
                ip_address="10.255.0.101",
                operating_system="Linux guest",
                vmid="101",
                node_type=ManagedNodeType.VM,
                environment=ServerEnvironment.LAB,
                tags=["legacy"],
                ssh_port=22,
                ssh_username="ubuntu",
                ssh_auth_method=ServerSshAuthMethod.KEY,
                status=ServerStatus.ONLINE,
                provider="proxmox",
                external_id="101",
                source="imported",
                managed=False,
                management_state=ManagementState.UNMANAGED,
                lifecycle_state=InventoryLifecycleState.UNMANAGED,
                sync_status=InventorySyncStatus.UNMANAGED,
                sync_state=InventorySyncStatus.UNMANAGED,
            )
        )

        result = await ProxmoxService(
            FakeProxmoxAdapter(),
            server_repository=repository,
            integration_id=integration_id,
            integration_name="Cluster A",
        ).sync_guests()

        servers = await repository.list_by_provider("proxmox")
        adopted = next(server for server in servers if server.hostname == "app-01")

        assert result.imported_count == 2
        assert result.updated_count == 1
        assert len(servers) == 3
        assert adopted.id == legacy.id
        assert adopted.integration_id == integration_id
        assert adopted.provider_metadata["integration_name"] == "Cluster A"


@pytest.mark.asyncio
async def test_proxmox_guest_sync_is_scoped_per_integration(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        first_id = "11111111-1111-1111-1111-111111111111"
        second_id = "22222222-2222-2222-2222-222222222222"

        await ProxmoxService(
            SecondFakeProxmoxAdapter(),
            server_repository=ServerRepository(db_session),
            integration_id=first_id,
            integration_name="Cluster A",
        ).sync_guests()
        await ProxmoxService(
            FakeProxmoxAdapter(),
            server_repository=ServerRepository(db_session),
            integration_id=second_id,
            integration_name="Cluster B",
        ).sync_guests()

        first_servers = await ServerRepository(db_session).list_by_provider_integration("proxmox", UUID(first_id))
        second_servers = await ServerRepository(db_session).list_by_provider_integration("proxmox", UUID(second_id))

        assert len(first_servers) == 3
        assert len(second_servers) == 3
        assert {server.integration_id for server in first_servers} != {server.integration_id for server in second_servers}
        assert all(server.provider_metadata["integration_name"] == "Cluster A" for server in first_servers)
        assert all(server.provider_metadata["integration_name"] == "Cluster B" for server in second_servers)


@pytest.mark.asyncio
async def test_proxmox_host_sync_reconnects_decommissioned_hypervisor(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        service = ProxmoxService(
            FakeProxmoxAdapter(),
            server_repository=ServerRepository(db_session),
            integration_id="22222222-2222-2222-2222-222222222222",
        )
        await service.sync_hosts()
        repository = ServerRepository(db_session)
        server = (await repository.list_by_provider("proxmox"))[0]
        server.managed = False
        server.management_state = ManagementState.RETIRED
        server.lifecycle_state = InventoryLifecycleState.DECOMMISSIONED
        await db_session.commit()

        result = await service.sync_hosts()
        reconnected = (await repository.list_by_provider("proxmox"))[0]

        assert result.updated_count == 1
        assert reconnected.managed is True
        assert reconnected.management_state == ManagementState.MANAGED
        assert reconnected.lifecycle_state == InventoryLifecycleState.MANAGED
