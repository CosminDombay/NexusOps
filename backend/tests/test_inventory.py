from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from backend.app.adapters.ssh import SshAdapter, SshExecutionResult
from backend.app.common.constants import (
    InventoryHealthStatus,
    InventorySyncStatus,
    ManagedNodeType,
    ManagementState,
    ServerEnvironment,
    ServerStatus,
)
from backend.app.modules.credentials.schemas import ResolvedCredential
from backend.app.modules.inventory.discovery import HostDiscoveryService
from backend.app.modules.inventory.models import ServerSshAuthMethod
from backend.app.modules.inventory.schemas import ServerRead
from backend.app.modules.proxmox.schemas import ProxmoxVmRead
from backend.app.modules.proxmox.service import ProxmoxService


class FakeDiscoverySshAdapter(SshAdapter):
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return "fake-discovery-ssh"

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
                "private_key_path": private_key_path,
                "private_key": private_key,
                "passphrase": passphrase,
                "input_data": input_data,
            }
        )
        return SshExecutionResult(
            exit_code=0,
            stdout="__NEXUSOPS_SECTION__:hostname\npve-01\n",
            stderr="",
        )

    async def upload_file(self, host: str, local_path: str, remote_path: str, user: str) -> None:
        raise NotImplementedError


class FakeCredentialService:
    async def resolve_credential(self, credential_id):
        return ResolvedCredential(
            id=credential_id,
            name="pve-root-password",
            credential_type="ssh_password",
            username="root",
            secret="proxmox-password",
        )


def server_payload(**overrides):
    payload = {
        "hostname": "app-01",
        "ip_address": "10.0.0.10",
        "operating_system": "Ubuntu 24.04 LTS",
        "vmid": "100",
        "environment": "development",
        "tags": ["api", "linux"],
        "ssh_port": 22,
        "ssh_username": "ubuntu",
        "status": "online",
        "provider": "proxmox",
    }
    payload.update(overrides)
    return payload


def test_inventory_crud_flow(client) -> None:
    create_response = client.post("/api/v1/servers", json=server_payload())
    assert create_response.status_code == 201
    created = create_response.json()
    server_id = created["id"]
    assert created["hostname"] == "app-01"
    assert created["managed"] is True
    assert created["node_type"] == "vm"
    assert created["management_state"] == "managed"
    assert created["lifecycle_state"] == "managed"
    assert created["sync_status"] == "unknown"
    assert created["sync_state"] == "unknown"
    assert {"ssh", "shell", "filesystem", "identity", "monitoring", "provisioning"}.issubset(
        set(created["capabilities"])
    )

    get_response = client.get(f"/api/v1/servers/{server_id}")
    assert get_response.status_code == 200
    assert get_response.json()["ip_address"] == "10.0.0.10"

    update_response = client.put(
        f"/api/v1/servers/{server_id}",
        json={"environment": "production", "tags": ["api", "critical"]},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["environment"] == "production"
    assert updated["tags"] == ["api", "critical"]

    list_response = client.get("/api/v1/servers", params={"environment": "production"})
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    search_response = client.get("/api/v1/servers", params={"search": "10.0.0"})
    assert search_response.status_code == 200
    assert len(search_response.json()) == 1

    delete_response = client.delete(f"/api/v1/servers/{server_id}")
    assert delete_response.status_code == 204

    missing_response = client.get(f"/api/v1/servers/{server_id}")
    assert missing_response.status_code == 404


def test_inventory_rejects_duplicate_hostname(client) -> None:
    first_response = client.post("/api/v1/servers", json=server_payload())
    assert first_response.status_code == 201

    duplicate_response = client.post(
        "/api/v1/servers",
        json=server_payload(ip_address="10.0.0.11"),
    )
    assert duplicate_response.status_code == 409


def test_inventory_rejects_duplicate_ip_address(client) -> None:
    first_response = client.post("/api/v1/servers", json=server_payload())
    assert first_response.status_code == 201

    duplicate_response = client.post(
        "/api/v1/servers",
        json=server_payload(hostname="app-02"),
    )
    assert duplicate_response.status_code == 409


def test_inventory_validates_ip_address_and_environment(client) -> None:
    bad_ip_response = client.post("/api/v1/servers", json=server_payload(ip_address="not-an-ip"))
    assert bad_ip_response.status_code == 422

    bad_environment_response = client.post(
        "/api/v1/servers",
        json=server_payload(hostname="app-03", ip_address="10.0.0.12", environment="sandbox"),
    )
    assert bad_environment_response.status_code == 422


def test_inventory_filters_by_provider(client) -> None:
    assert client.post("/api/v1/servers", json=server_payload()).status_code == 201
    assert (
        client.post(
            "/api/v1/servers",
            json=server_payload(
                hostname="baremetal-01",
                ip_address="10.0.0.20",
                provider="manual",
                vmid=None,
            ),
        ).status_code
        == 201
    )

    response = client.get("/api/v1/servers", params={"provider": "manual"})
    assert response.status_code == 200
    servers = response.json()
    assert len(servers) == 1
    assert servers[0]["hostname"] == "baremetal-01"


def test_inventory_classifies_proxmox_host_without_vmid_as_hypervisor(client) -> None:
    response = client.post(
        "/api/v1/servers",
        json=server_payload(
            hostname="pve-01",
            ip_address="10.0.0.21",
            vmid=None,
            provider="proxmox",
        ),
    )

    assert response.status_code == 201
    assert response.json()["node_type"] == "hypervisor"


def test_inventory_requires_password_for_password_auth(client) -> None:
    response = client.post(
        "/api/v1/servers",
        json=server_payload(
            hostname="password-host",
            ip_address="10.0.0.30",
            ssh_auth_method="password",
        ),
    )

    assert response.status_code == 422


def test_inventory_accepts_password_auth_without_echoing_secret(client) -> None:
    response = client.post(
        "/api/v1/servers",
        json=server_payload(
            hostname="password-host",
            ip_address="10.0.0.30",
            ssh_auth_method="password",
            ssh_password="secret",
        ),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["ssh_auth_method"] == "password"
    assert "ssh_password" not in payload


def test_inventory_update_password_auth_response_does_not_require_echoed_secret(client) -> None:
    response = client.post(
        "/api/v1/servers",
        json=server_payload(
            hostname="password-update-host",
            ip_address="10.0.0.31",
            ssh_auth_method="password",
            ssh_password="secret",
        ),
    )
    assert response.status_code == 201
    server_id = response.json()["id"]

    update_response = client.put(
        f"/api/v1/servers/{server_id}",
        json={"tags": ["edited"]},
    )

    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["ssh_auth_method"] == "password"
    assert "ssh_password" not in payload


def test_inventory_read_tolerates_password_auth_without_current_secret() -> None:
    now = datetime.now(UTC)
    server = SimpleNamespace(
        id=uuid4(),
        hostname="orphaned-password-host",
        ip_address="10.0.0.32",
        operating_system="Ubuntu",
        vmid=None,
        node_type=ManagedNodeType.PHYSICAL,
        environment=ServerEnvironment.LAB,
        tags=[],
        ssh_port=22,
        ssh_username="ubuntu",
        ssh_auth_method=ServerSshAuthMethod.PASSWORD,
        ssh_password=None,
        ssh_private_key_path=None,
        trusted_ssh_host_key_sha256=None,
        trusted_ssh_host_key_accepted_at=None,
        credential_id=None,
        status=ServerStatus.UNKNOWN,
        provider="manual",
        external_id=None,
        source="manual",
        integration_id=None,
        source_type="manual",
        managed=True,
        management_state=ManagementState.MANAGED,
        lifecycle_state="managed",
        sync_status=InventorySyncStatus.UNKNOWN,
        sync_state=InventorySyncStatus.UNKNOWN,
        provider_node=None,
        provider_type=None,
        monitoring_interface=None,
        monitoring_target=None,
        monitoring_strategy=None,
        provider_metadata={},
        sync_metadata={},
        capabilities=[],
        last_seen_at=None,
        last_sync_at=None,
        stale_since=None,
        last_health_check_at=None,
        last_health_status=InventoryHealthStatus.UNKNOWN,
        last_health_error=None,
        created_at=now,
        updated_at=now,
        runtime_state=None,
    )

    payload = ServerRead.model_validate(server)

    assert payload.hostname == "orphaned-password-host"
    assert payload.ssh_auth_method == ServerSshAuthMethod.PASSWORD
    assert payload.credential_id is None


def test_credential_delete_moves_referenced_credential_to_trash(client) -> None:
    credential_response = client.post(
        "/api/v1/credentials",
        json={
            "name": "inventory-ssh-password",
            "credential_type": "ssh_password",
            "username": "ubuntu",
            "secret": "secret-password",
        },
    )
    assert credential_response.status_code == 201
    credential_id = credential_response.json()["id"]

    server_response = client.post(
        "/api/v1/servers",
        json=server_payload(
            hostname="credential-backed-host",
            ip_address="10.0.0.33",
            ssh_auth_method="password",
            credential_id=credential_id,
        ),
    )
    assert server_response.status_code == 201

    delete_response = client.delete(f"/api/v1/credentials/{credential_id}")

    assert delete_response.status_code == 200
    deleted_payload = delete_response.json()
    assert deleted_payload["deleted_at"] is not None
    assert deleted_payload["reference_count"] == 1
    assert all(item["id"] != credential_id for item in client.get("/api/v1/credentials").json())

    trash_response = client.get("/api/v1/trash")

    assert trash_response.status_code == 200
    credential_group = next(group for group in trash_response.json()["groups"] if group["item_type"] == "credential")
    trashed_item = credential_group["items"][0]
    assert trashed_item["item_id"] == credential_id
    assert trashed_item["metadata"]["credential_type"] == "ssh_password"
    assert trashed_item["metadata"]["scope"] == "global"
    assert trashed_item["reference_count"] == 1

    usage_response = client.get(f"/api/v1/trash/credential/{credential_id}/references")

    assert usage_response.status_code == 200
    assert usage_response.json()["references"][0]["reference_type"] == "inventory_server"

    purge_response = client.delete(f"/api/v1/trash/credential/{credential_id}/purge")

    assert purge_response.status_code == 409
    assert "referenced" in purge_response.json()["detail"]

    restore_response = client.post(f"/api/v1/trash/credential/{credential_id}/restore")

    assert restore_response.status_code == 200
    assert restore_response.json()["item_type"] == "credential"
    assert restore_response.json()["item_id"] == credential_id
    assert client.get("/api/v1/trash").json()["groups"] == []


def test_credential_can_be_permanently_purged_after_trash_when_unreferenced(client) -> None:
    credential_response = client.post(
        "/api/v1/credentials",
        json={
            "name": "unused-ssh-password",
            "credential_type": "ssh_password",
            "username": "ubuntu",
            "secret": "secret-password",
        },
    )
    assert credential_response.status_code == 201
    credential_id = credential_response.json()["id"]

    delete_response = client.delete(f"/api/v1/credentials/{credential_id}")

    assert delete_response.status_code == 200
    assert delete_response.json()["deleted_at"] is not None

    trash_response = client.get("/api/v1/trash")

    assert trash_response.status_code == 200
    credential_group = next(group for group in trash_response.json()["groups"] if group["item_type"] == "credential")
    assert credential_group["items"][0]["item_id"] == credential_id

    purge_response = client.delete(f"/api/v1/trash/credential/{credential_id}/purge")

    assert purge_response.status_code == 204
    assert client.get(f"/api/v1/credentials/{credential_id}/usage").status_code == 404


@pytest.mark.asyncio
async def test_host_discovery_uses_attached_ssh_credential() -> None:
    credential_id = uuid4()
    server = SimpleNamespace(
        hostname="pve-01",
        ip_address="10.0.0.50",
        operating_system="Proxmox VE",
        ssh_port=22,
        ssh_username="inventory-user",
        ssh_auth_method=ServerSshAuthMethod.KEY,
        ssh_password=None,
        ssh_private_key_path=None,
        credential_id=credential_id,
    )
    adapter = FakeDiscoverySshAdapter()
    service = HostDiscoveryService(adapter, credential_service=FakeCredentialService())

    result = await service.system(server)

    assert result.hostname == "pve-01"
    assert adapter.calls[0]["user"] == "root"
    assert adapter.calls[0]["password"] == "proxmox-password"
    assert adapter.calls[0]["private_key_path"] is None
    assert adapter.calls[0]["private_key"] is None


@pytest.mark.asyncio
async def test_host_docker_discovery_uses_sudo_fallback() -> None:
    server = SimpleNamespace(
        hostname="docker-01",
        ip_address="10.0.0.51",
        operating_system="Ubuntu",
        ssh_port=22,
        ssh_username="ubuntu",
        ssh_auth_method=ServerSshAuthMethod.KEY,
        ssh_password=None,
        ssh_private_key_path=None,
        credential_id=None,
    )
    adapter = FakeDiscoverySshAdapter()
    service = HostDiscoveryService(adapter)

    await service.docker(server)

    command = adapter.calls[0]["command"]
    assert "nexusops_docker()" in command
    assert "if sudo docker \"$@\" 2>\"$sudo_err_file\"; then" in command
    assert "nexusops_docker version" in command
    assert "nexusops_docker ps --format" in command
    assert "nexusops_docker network ls" in command


@pytest.mark.asyncio
async def test_host_docker_discovery_feeds_sudo_credential() -> None:
    credential_id = uuid4()
    server = SimpleNamespace(
        hostname="docker-credential-01",
        ip_address="10.0.0.52",
        operating_system="Ubuntu",
        ssh_port=22,
        ssh_username="ubuntu",
        ssh_auth_method=ServerSshAuthMethod.KEY,
        ssh_password=None,
        ssh_private_key_path=None,
        credential_id=credential_id,
    )
    adapter = FakeDiscoverySshAdapter()
    service = HostDiscoveryService(adapter, credential_service=FakeCredentialService())

    await service.docker(server)

    assert adapter.calls[0]["password"] == "proxmox-password"
    assert adapter.calls[0]["input_data"] == "proxmox-password\n"
    assert "NEXUSOPS_ASKPASS=$(mktemp)" in adapter.calls[0]["command"]
    assert "sudo() { SUDO_ASKPASS=\"$NEXUSOPS_ASKPASS\" command sudo -A -p '' \"$@\"; }" in adapter.calls[0]["command"]
    assert "nexusops_docker version" in adapter.calls[0]["command"]


def test_inventory_archives_without_deleting_provider_metadata(client) -> None:
    create_response = client.post(
        "/api/v1/servers",
        json=server_payload(external_id="100", provider_node="hellgate", provider_type="qemu"),
    )
    assert create_response.status_code == 201
    server_id = create_response.json()["id"]

    archive_response = client.post(f"/api/v1/servers/{server_id}/archive")
    assert archive_response.status_code == 200
    archived = archive_response.json()
    assert archived["managed"] is False
    assert archived["management_state"] == "retired"
    assert archived["lifecycle_state"] == "archived"
    assert archived["sync_status"] == "archived"
    assert archived["sync_state"] == "archived"
    assert archived["external_id"] == "100"

    list_response = client.get("/api/v1/servers")
    assert list_response.status_code == 200
    assert list_response.json() == []

    historical_response = client.get("/api/v1/servers", params={"include_inactive": True})
    assert historical_response.status_code == 200
    assert historical_response.json()[0]["id"] == server_id


def test_inventory_decommission_and_restore_lifecycle(client) -> None:
    create_response = client.post(
        "/api/v1/servers",
        json=server_payload(hostname="retire-me", ip_address="10.0.0.40"),
    )
    assert create_response.status_code == 201
    server_id = create_response.json()["id"]

    decommission_response = client.post(f"/api/v1/servers/{server_id}/decommission")
    assert decommission_response.status_code == 200
    decommissioned = decommission_response.json()
    assert decommissioned["managed"] is False
    assert decommissioned["management_state"] == "retired"
    assert decommissioned["lifecycle_state"] == "decommissioned"
    assert decommissioned["sync_state"] == "archived"
    assert decommissioned["last_health_status"] == "archived"

    active_response = client.get("/api/v1/servers")
    assert active_response.status_code == 200
    assert active_response.json() == []

    historical_response = client.get("/api/v1/servers", params={"include_inactive": True})
    assert historical_response.status_code == 200
    assert historical_response.json()[0]["id"] == server_id

    restore_response = client.post(f"/api/v1/servers/{server_id}/restore")
    assert restore_response.status_code == 200
    restored = restore_response.json()
    assert restored["managed"] is True
    assert restored["management_state"] == "managed"
    assert restored["lifecycle_state"] == "managed"
    assert restored["sync_state"] == "unknown"


def test_inventory_unmanage_removes_node_from_managed_inventory(client) -> None:
    create_response = client.post(
        "/api/v1/servers",
        json=server_payload(hostname="manual-node", ip_address="10.0.0.41"),
    )
    assert create_response.status_code == 201
    server_id = create_response.json()["id"]

    unmanage_response = client.post(f"/api/v1/servers/{server_id}/unmanage")
    assert unmanage_response.status_code == 200
    unmanaged = unmanage_response.json()
    assert unmanaged["managed"] is False
    assert unmanaged["management_state"] == "unmanaged"
    assert unmanaged["lifecycle_state"] == "unmanaged"
    assert unmanaged["sync_state"] == "unmanaged"

    list_response = client.get("/api/v1/servers")
    assert list_response.status_code == 200
    assert list_response.json() == []

    discovery_response = client.get("/api/v1/servers", params={"include_unmanaged": True})
    assert discovery_response.status_code == 200
    assert discovery_response.json()[0]["id"] == server_id


def test_inventory_import_restores_archived_proxmox_record(client, monkeypatch) -> None:
    async def fake_list_vms(self):
        return [
            ProxmoxVmRead(
                integration_id="11111111-1111-1111-1111-111111111111",
                vm_id=106,
                name="hds-tool",
                node="hellgate",
                type="qemu",
                status="running",
                ip_address="192.168.50.15",
            )
        ]

    monkeypatch.setattr(ProxmoxService, "list_vms", fake_list_vms)
    integration_response = client.post(
        "/api/v1/integrations",
        json={
            "name": "Proxmox Test",
            "type": "infrastructure_provider",
            "provider_type": "proxmox",
            "enabled": True,
            "config": {
                "api_url": "https://pve.example:8006/api2/json",
                "token_id": "root@pam!test",
                "token_secret": "secret",
                "verify_ssl": False,
            },
            "credential_refs": {},
        },
    )
    assert integration_response.status_code == 201
    integration_id = integration_response.json()["id"]

    create_response = client.post(
        "/api/v1/servers",
        json=server_payload(
            hostname="hds-tool",
            ip_address="192.168.50.15",
            provider="proxmox",
        ),
    )
    assert create_response.status_code == 201
    server_id = create_response.json()["id"]
    assert client.post(f"/api/v1/servers/{server_id}/archive").status_code == 200

    import_response = client.post(
        "/api/v1/servers/sync/proxmox/import",
        json={
            "integration_id": integration_id,
            "vm_id": 106,
            "node": "hellgate",
            "vm_type": "qemu",
            "hostname": "hds-tool",
            "ip_address": "192.168.50.15",
            "operating_system": "Ubuntu LTS 24.04",
            "environment": "development",
            "tags": ["restored"],
            "ssh_port": 22,
            "ssh_username": "cerberus",
            "ssh_auth_method": "key",
        },
    )

    assert import_response.status_code == 201
    restored = import_response.json()
    assert restored["id"] == server_id
    assert restored["lifecycle_state"] == "managed"
    assert restored["sync_status"] in {"synced", "unknown"}
    assert restored["external_id"] == "106"
    assert restored["managed"] is True


def test_inventory_import_promotes_unmanaged_proxmox_record(client, monkeypatch) -> None:
    async def fake_list_vms(self):
        return [
            ProxmoxVmRead(
                integration_id="11111111-1111-1111-1111-111111111111",
                vm_id=106,
                name="hds-tool",
                node="hellgate",
                type="qemu",
                status="running",
                ip_address="192.168.50.15",
            )
        ]

    monkeypatch.setattr(ProxmoxService, "list_vms", fake_list_vms)
    integration_response = client.post(
        "/api/v1/integrations",
        json={
            "name": "Proxmox Test",
            "type": "infrastructure_provider",
            "provider_type": "proxmox",
            "enabled": True,
            "config": {
                "api_url": "https://pve.example:8006/api2/json",
                "token_id": "root@pam!test",
                "token_secret": "secret",
                "verify_ssl": False,
            },
            "credential_refs": {},
        },
    )
    assert integration_response.status_code == 201
    integration_id = integration_response.json()["id"]

    create_response = client.post(
        "/api/v1/servers",
        json=server_payload(
            hostname="hds-tool",
            ip_address="192.168.50.15",
            provider="proxmox",
            external_id="106",
            vmid="106",
            integration_id=integration_id,
            provider_node="hellgate",
            provider_type="qemu",
        ),
    )
    assert create_response.status_code == 201
    server_id = create_response.json()["id"]
    assert client.post(f"/api/v1/servers/{server_id}/unmanage").status_code == 200

    import_response = client.post(
        "/api/v1/servers/sync/proxmox/import",
        json={
            "integration_id": integration_id,
            "vm_id": 106,
            "node": "hellgate",
            "vm_type": "qemu",
            "hostname": "hds-tool",
            "ip_address": "192.168.50.15",
            "operating_system": "Ubuntu LTS 24.04",
            "environment": "development",
            "tags": ["promoted"],
            "ssh_port": 22,
            "ssh_username": "cerberus",
            "ssh_auth_method": "key",
        },
    )

    assert import_response.status_code == 201
    promoted = import_response.json()
    assert promoted["id"] == server_id
    assert promoted["lifecycle_state"] == "managed"
    assert promoted["sync_status"] in {"synced", "unknown"}
    assert promoted["external_id"] == "106"
    assert promoted["managed"] is True
    assert promoted["provider_metadata"]["promoted_from_discovery"] is True


def test_proxmox_sanitize_removes_only_discovered_unmanaged_guests(client) -> None:
    stale_response = client.post(
        "/api/v1/servers",
        json=server_payload(
            hostname="stale-guest",
            ip_address="10.0.0.31",
            vmid="210",
            external_id="210",
            node_type="vm",
            managed=False,
            management_state="unmanaged",
            lifecycle_state="unmanaged",
            sync_status="unmanaged",
            sync_state="unmanaged",
            tags=["source:proxmox", "qemu", "discovered"],
            provider="proxmox",
            provider_type="qemu",
            sync_metadata={"last_sync_reason": "guest_sync"},
        ),
    )
    assert stale_response.status_code == 201
    stale_id = stale_response.json()["id"]

    managed_response = client.post(
        "/api/v1/servers",
        json=server_payload(
            hostname="managed-guest",
            ip_address="10.0.0.32",
            vmid="211",
            external_id="211",
            node_type="vm",
            provider="proxmox",
            provider_type="qemu",
        ),
    )
    assert managed_response.status_code == 201
    managed_id = managed_response.json()["id"]

    sanitize_response = client.post("/api/v1/proxmox/inventory/sanitize-discovered")

    assert sanitize_response.status_code == 200
    result = sanitize_response.json()
    assert result["deleted_count"] == 1
    assert result["deleted"] == ["stale-guest"]
    assert client.get(f"/api/v1/servers/{stale_id}").status_code == 404
    assert client.get(f"/api/v1/servers/{managed_id}").status_code == 200


def test_proxmox_sanitize_dry_run_keeps_records(client) -> None:
    stale_response = client.post(
        "/api/v1/servers",
        json=server_payload(
            hostname="dry-run-stale-guest",
            ip_address="10.0.0.33",
            vmid="212",
            external_id="212",
            node_type="vm",
            managed=False,
            management_state="unmanaged",
            lifecycle_state="unmanaged",
            sync_status="unmanaged",
            sync_state="unmanaged",
            tags=["source:proxmox", "qemu", "discovered"],
            provider="proxmox",
            provider_type="qemu",
            sync_metadata={"last_sync_reason": "guest_sync"},
        ),
    )
    assert stale_response.status_code == 201
    stale_id = stale_response.json()["id"]

    sanitize_response = client.post("/api/v1/proxmox/inventory/sanitize-discovered?dry_run=true")

    assert sanitize_response.status_code == 200
    result = sanitize_response.json()
    assert result["dry_run"] is True
    assert result["deleted_count"] == 1
    assert result["deleted"] == ["dry-run-stale-guest"]
    assert client.get(f"/api/v1/servers/{stale_id}").status_code == 200


def test_server_credential_readiness_reports_sudo_and_docker_signals(client) -> None:
    response = client.post(
        "/api/v1/servers",
        json=server_payload(
            hostname="readiness-host",
            ip_address="10.0.0.34",
            ssh_auth_method="password",
            ssh_password="secret",
            capabilities=["docker"],
        ),
    )
    assert response.status_code == 201
    server_id = response.json()["id"]

    readiness_response = client.get(f"/api/v1/servers/{server_id}/readiness")

    assert readiness_response.status_code == 200
    readiness = readiness_response.json()
    assert readiness["ssh_ready"] is True
    assert readiness["sudo_ready"] is True
    assert readiness["docker_ready"] is True
    assert {signal["key"] for signal in readiness["signals"]} >= {"ssh", "sudo", "docker"}
