from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy import delete, update

from backend.app.modules.deployments.models import DeploymentTarget
from backend.app.modules.inventory.models import (
    InventoryLifecycleState,
    InventoryHealthStatus,
    InventorySyncStatus,
    ManagedNodeType,
    ManagementState,
    Server,
    ServerEnvironment,
)
from backend.app.modules.provisioning.models import ProvisioningRequest, VirtualMachine
from backend.app.modules.workflows.models import WorkflowRun
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.schemas import ProxmoxInventoryImport, ServerCreate, ServerUpdate
from backend.app.modules.proxmox.schemas import ProxmoxVmRead
from backend.app.modules.runtime_state.repository import (
    NodeRuntimeSnapshotRepository,
    RuntimeRefreshEventRepository,
    RuntimeRefreshStatusRepository,
)
from backend.app.modules.runtime_state.snapshots import RuntimeSnapshotService

logger = structlog.get_logger(__name__)


class InventoryConflictError(Exception):
    """Raised when a server violates inventory uniqueness rules."""


class ServerNotFoundError(Exception):
    """Raised when a server does not exist."""


class InventoryService:
    """Application service for server inventory workflows."""

    def __init__(self, repository: ServerRepository) -> None:
        self.repository = repository
        self.runtime_snapshots = RuntimeSnapshotService(
            NodeRuntimeSnapshotRepository(repository.session),
            status_repository=RuntimeRefreshStatusRepository(repository.session),
            event_repository=RuntimeRefreshEventRepository(repository.session),
        )

    async def create_server(self, payload: ServerCreate) -> Server:
        await self._ensure_unique(hostname=payload.hostname, ip_address=payload.ip_address)

        data = payload.model_dump()
        if "node_type" not in payload.model_fields_set:
            data["node_type"] = None
        data = self._managed_node_defaults(data)
        server = Server(**data)
        try:
            created = await self.repository.create(server)
            await self.runtime_snapshots.refresh_inventory_snapshot(created, commit=False)
            await self.repository.session.commit()
        except IntegrityError as exc:
            await self.repository.session.rollback()
            logger.warning(
                "server_create_failed",
                hostname=payload.hostname,
                ip_address=payload.ip_address,
                reason="integrity_error",
            )
            raise InventoryConflictError("Hostname or IP address already exists") from exc

        logger.info(
            "server_created",
            server_id=str(created.id),
            hostname=created.hostname,
            ip_address=created.ip_address,
            environment=created.environment,
            provider=created.provider,
        )
        return created

    async def import_proxmox_vm(
        self,
        payload: ProxmoxInventoryImport,
        *,
        discovered_vm: ProxmoxVmRead | None = None,
    ) -> Server:
        vm_name = discovered_vm.name if discovered_vm else payload.hostname
        existing = await self.repository.get_by_provider_external_id("proxmox", str(payload.vm_id))
        if existing is None:
            existing = await self.repository.get_by_hostname(payload.hostname)
        if existing is None:
            existing = await self.repository.get_by_ip_address(payload.ip_address)

        if existing:
            if existing.lifecycle_state in {
                InventoryLifecycleState.ARCHIVED,
                InventoryLifecycleState.DECOMMISSIONED,
            }:
                return await self._restore_archived_proxmox_server(
                    existing,
                    payload=payload,
                    discovered_vm=discovered_vm,
                )
            raise InventoryConflictError("Proxmox VM is already linked to inventory")

        await self._ensure_unique(hostname=payload.hostname, ip_address=payload.ip_address)

        server = Server(
            hostname=payload.hostname,
            ip_address=payload.ip_address,
            operating_system=payload.operating_system,
            vmid=str(payload.vm_id),
            environment=payload.environment,
            tags=[*payload.tags, "source:imported", "managed"],
            ssh_port=payload.ssh_port,
            ssh_username=payload.ssh_username,
            ssh_auth_method=payload.ssh_auth_method,
            ssh_password=payload.ssh_password,
            ssh_private_key_path=payload.ssh_private_key_path,
            credential_id=payload.credential_id,
            status=self._server_status_from_vm(discovered_vm.status if discovered_vm else "unknown"),
            provider="proxmox",
            external_id=str(payload.vm_id),
            source="imported",
            managed=True,
            node_type=self._node_type_from_provider_type(payload.vm_type),
            management_state=ManagementState.MANAGED,
            lifecycle_state=InventoryLifecycleState.MANAGED,
            sync_status=InventorySyncStatus.SYNCED if discovered_vm else InventorySyncStatus.UNKNOWN,
            sync_state=InventorySyncStatus.SYNCED if discovered_vm else InventorySyncStatus.UNKNOWN,
            provider_node=payload.node,
            provider_type=payload.vm_type,
            provider_metadata={
                "vm_name": vm_name,
                "detected_ip_address": discovered_vm.ip_address if discovered_vm else None,
            },
            last_seen_at=datetime.now(UTC) if discovered_vm else None,
        )

        try:
            created = await self.repository.create(server)
            await self.runtime_snapshots.refresh_inventory_snapshot(created, commit=False)
            await self.repository.session.commit()
        except IntegrityError as exc:
            await self.repository.session.rollback()
            raise InventoryConflictError("Hostname, IP address, or provider link already exists") from exc

        logger.info(
            "proxmox_vm_imported",
            server_id=str(created.id),
            vm_id=payload.vm_id,
            hostname=created.hostname,
        )
        return created

    async def _restore_archived_proxmox_server(
        self,
        server: Server,
        *,
        payload: ProxmoxInventoryImport,
        discovered_vm: ProxmoxVmRead | None,
    ) -> Server:
        vm_name = discovered_vm.name if discovered_vm else payload.hostname
        server.hostname = payload.hostname
        server.ip_address = payload.ip_address
        server.operating_system = payload.operating_system
        server.vmid = str(payload.vm_id)
        server.environment = payload.environment
        server.tags = [*payload.tags, "source:imported", "managed"]
        server.ssh_port = payload.ssh_port
        server.ssh_username = payload.ssh_username
        server.ssh_auth_method = payload.ssh_auth_method
        server.ssh_password = payload.ssh_password
        server.ssh_private_key_path = payload.ssh_private_key_path
        server.credential_id = payload.credential_id
        server.status = self._server_status_from_vm(discovered_vm.status if discovered_vm else "unknown")
        server.provider = "proxmox"
        server.external_id = str(payload.vm_id)
        server.source = "imported"
        server.managed = True
        server.node_type = self._node_type_from_provider_type(payload.vm_type)
        server.management_state = ManagementState.MANAGED
        server.lifecycle_state = InventoryLifecycleState.MANAGED
        server.sync_status = InventorySyncStatus.SYNCED if discovered_vm else InventorySyncStatus.UNKNOWN
        server.sync_state = server.sync_status
        server.provider_node = payload.node
        server.provider_type = payload.vm_type
        server.provider_metadata = {"vm_name": vm_name, "restored_from_archive": True}
        if discovered_vm and discovered_vm.ip_address:
            server.provider_metadata["detected_ip_address"] = discovered_vm.ip_address
        server.last_seen_at = datetime.now(UTC) if discovered_vm else None

        await self.repository.session.commit()
        await self.repository.session.refresh(server)
        await self.runtime_snapshots.refresh_inventory_snapshot(server)
        logger.info(
            "proxmox_vm_restored_from_archive",
            server_id=str(server.id),
            vm_id=payload.vm_id,
            hostname=server.hostname,
        )
        return server

    async def update_server(self, server_id: UUID, payload: ServerUpdate) -> Server:
        server = await self.repository.get_by_id(server_id)
        if server is None:
            logger.warning("server_update_failed", server_id=str(server_id), reason="not_found")
            raise ServerNotFoundError("Server not found")

        update_data = payload.model_dump(exclude_unset=True)
        await self._ensure_unique(
            hostname=update_data.get("hostname"),
            ip_address=update_data.get("ip_address"),
            exclude_id=server_id,
        )

        for key, value in update_data.items():
            setattr(server, key, value)
        self._normalize_management_fields(server)

        try:
            await self.repository.session.flush()
            await self.repository.session.refresh(server)
            await self.runtime_snapshots.refresh_inventory_snapshot(server, commit=False)
            await self.repository.session.commit()
        except IntegrityError as exc:
            await self.repository.session.rollback()
            logger.warning("server_update_failed", server_id=str(server_id), reason="integrity_error")
            raise InventoryConflictError("Hostname or IP address already exists") from exc

        logger.info("server_updated", server_id=str(server.id), fields=list(update_data.keys()))
        return server

    async def archive_server(self, server_id: UUID) -> Server:
        server = await self.repository.get_by_id(server_id)
        if server is None:
            raise ServerNotFoundError("Server not found")

        await self._archive_existing_server(server)
        logger.info("server_archived", server_id=str(server.id), hostname=server.hostname)
        return server

    async def decommission_server(self, server_id: UUID) -> Server:
        server = await self.repository.get_by_id(server_id)
        if server is None:
            raise ServerNotFoundError("Server not found")

        server.managed = False
        server.management_state = ManagementState.RETIRED
        server.lifecycle_state = InventoryLifecycleState.DECOMMISSIONED
        server.sync_status = InventorySyncStatus.ARCHIVED
        server.sync_state = InventorySyncStatus.ARCHIVED
        server.last_health_status = InventoryHealthStatus.ARCHIVED
        server.provider_metadata = {
            **server.provider_metadata,
            "decommissioned_at": datetime.now(UTC).isoformat(),
        }
        await self.repository.session.commit()
        await self.repository.session.refresh(server)
        await self.runtime_snapshots.refresh_inventory_snapshot(server)
        logger.info("server_decommissioned", server_id=str(server.id), hostname=server.hostname)
        return server

    async def restore_server(self, server_id: UUID) -> Server:
        server = await self.repository.get_by_id(server_id)
        if server is None:
            raise ServerNotFoundError("Server not found")

        server.managed = True
        server.management_state = ManagementState.MANAGED
        server.lifecycle_state = (
            InventoryLifecycleState.PROVISIONED
            if server.source == "provisioned"
            else InventoryLifecycleState.MANAGED
        )
        server.sync_status = InventorySyncStatus.UNKNOWN
        server.sync_state = InventorySyncStatus.UNKNOWN
        server.last_health_status = InventoryHealthStatus.UNKNOWN
        server.provider_metadata = {
            **server.provider_metadata,
            "restored_at": datetime.now(UTC).isoformat(),
        }
        await self.repository.session.commit()
        await self.repository.session.refresh(server)
        await self.runtime_snapshots.refresh_inventory_snapshot(server)
        logger.info("server_restored", server_id=str(server.id), hostname=server.hostname)
        return server

    async def mark_unmanaged(self, server_id: UUID) -> Server:
        server = await self.repository.get_by_id(server_id)
        if server is None:
            raise ServerNotFoundError("Server not found")

        server.managed = False
        server.management_state = ManagementState.UNMANAGED
        server.lifecycle_state = InventoryLifecycleState.UNMANAGED
        server.sync_status = InventorySyncStatus.UNMANAGED
        server.sync_state = InventorySyncStatus.UNMANAGED
        await self.repository.session.commit()
        await self.repository.session.refresh(server)
        await self.runtime_snapshots.refresh_inventory_snapshot(server)
        logger.info("server_marked_unmanaged", server_id=str(server.id), hostname=server.hostname)
        return server

    async def delete_server(self, server_id: UUID) -> None:
        server = await self.repository.get_by_id(server_id)
        if server is None:
            logger.warning("server_delete_failed", server_id=str(server_id), reason="not_found")
            raise ServerNotFoundError("Server not found")

        try:
            server.lifecycle_state = InventoryLifecycleState.DELETING
            await self.repository.session.flush()
            await self._cleanup_server_references(server_id)
            await self.repository.delete(server)
            await self.repository.session.commit()
            logger.info("server_deleted", server_id=str(server_id), hostname=server.hostname)
        except IntegrityError:
            await self.repository.session.rollback()
            server = await self.repository.get_by_id(server_id)
            if server is None:
                return
            await self._archive_existing_server(server)
            logger.info(
                "server_archived_instead_of_deleted",
                server_id=str(server_id),
                hostname=server.hostname,
                reason="referenced_by_history",
            )

    async def _cleanup_server_references(self, server_id: UUID) -> None:
        await self.repository.session.execute(
            update(ProvisioningRequest)
            .where(ProvisioningRequest.server_id == server_id)
            .values(server_id=None)
        )
        await self.repository.session.execute(
            update(VirtualMachine)
            .where(VirtualMachine.server_id == server_id)
            .values(server_id=None)
        )
        await self.repository.session.execute(
            update(WorkflowRun)
            .where(WorkflowRun.target_server_id == server_id)
            .values(target_server_id=None)
        )
        await self.repository.session.execute(delete(DeploymentTarget).where(DeploymentTarget.server_id == server_id))

    async def _archive_existing_server(self, server: Server) -> None:
        server.managed = False
        server.management_state = ManagementState.RETIRED
        server.lifecycle_state = InventoryLifecycleState.ARCHIVED
        server.sync_status = InventorySyncStatus.ARCHIVED
        server.sync_state = InventorySyncStatus.ARCHIVED
        server.last_health_status = InventoryHealthStatus.ARCHIVED
        await self.repository.session.commit()
        await self.repository.session.refresh(server)
        await self.runtime_snapshots.refresh_inventory_snapshot(server)
        await self.runtime_snapshots.refresh_inventory_snapshot(server)

    async def get_server(self, server_id: UUID) -> Server:
        server = await self.repository.get_by_id(server_id)
        if server is None:
            raise ServerNotFoundError("Server not found")
        return await self.runtime_snapshots.attach_snapshot(server)

    async def list_servers(
        self,
        *,
        environment: ServerEnvironment | None = None,
        provider: str | None = None,
        search: str | None = None,
        include_inactive: bool = False,
    ) -> list[Server]:
        servers = await self.repository.list(
            environment=environment,
            provider=provider,
            search=search,
            include_inactive=include_inactive,
        )
        return await self.runtime_snapshots.attach_snapshots(servers)

    async def reconcile_proxmox_inventory(
        self,
        discovered_vms: list[ProxmoxVmRead],
    ) -> list[Server]:
        by_external_id = {str(vm.vm_id): vm for vm in discovered_vms}
        by_hostname = {vm.name: vm for vm in discovered_vms}
        changed: list[Server] = []

        for server in await self.repository.list_by_provider("proxmox"):
            if server.lifecycle_state in {
                InventoryLifecycleState.ARCHIVED,
                InventoryLifecycleState.DECOMMISSIONED,
                InventoryLifecycleState.DELETED,
            }:
                continue

            vm = by_external_id.get(server.external_id or server.vmid or "") or by_hostname.get(
                server.hostname
            )
            if vm is None:
                server.sync_status = InventorySyncStatus.ORPHANED
            else:
                server.external_id = str(vm.vm_id)
                server.vmid = str(vm.vm_id)
                server.provider_node = vm.node
                server.provider_type = vm.type
                server.node_type = self._node_type_from_provider_type(vm.type)
                server.last_seen_at = datetime.now(UTC)
                previous_detected_ip = server.provider_metadata.get("detected_ip_address")
                server.provider_metadata = {
                    **server.provider_metadata,
                    "vm_name": vm.name,
                    "vm_status": vm.status,
                    "detected_ip_address": vm.ip_address,
                }
                if self._should_apply_detected_ip(server, vm, previous_detected_ip):
                    server.ip_address = vm.ip_address
                server.sync_status = self._sync_status_for_match(server, vm)
                server.sync_state = server.sync_status
            changed.append(server)

        if changed:
            await self.runtime_snapshots.refresh_inventory_snapshots(changed, commit=False)
            await self.repository.session.commit()

        return changed

    @staticmethod
    def match_discovered_vm(
        vm: ProxmoxVmRead,
        inventory: list[Server],
    ) -> tuple[Server | None, InventorySyncStatus, list[str]]:
        notes: list[str] = []
        match = next(
            (
                server
                for server in inventory
                if server.provider == "proxmox"
                and (server.external_id == str(vm.vm_id) or server.vmid == str(vm.vm_id))
            ),
            None,
        )
        if match is None:
            match = next((server for server in inventory if server.hostname == vm.name), None)
            if match:
                notes.append("Matched by hostname; provider VMID is not linked yet.")

        if match is None and vm.ip_address:
            match = next((server for server in inventory if server.ip_address == vm.ip_address), None)
            if match:
                notes.append("Matched by IP address; provider VMID is not linked yet.")

        if match is None:
            return None, InventorySyncStatus.UNMANAGED, ["Discovered in Proxmox but not imported."]

        status = InventoryService._sync_status_for_match(match, vm)
        if match.hostname != vm.name:
            notes.append(f"Inventory hostname differs from Proxmox name ({vm.name}).")
        if match.lifecycle_state in {InventoryLifecycleState.ARCHIVED, InventoryLifecycleState.DECOMMISSIONED}:
            notes.append(f"Inventory record is {match.lifecycle_state.value}.")

        return match, status, notes

    @staticmethod
    def _sync_status_for_match(server: Server, vm: ProxmoxVmRead) -> InventorySyncStatus:
        if server.lifecycle_state in {InventoryLifecycleState.ARCHIVED, InventoryLifecycleState.DECOMMISSIONED}:
            return InventorySyncStatus.ARCHIVED
        if server.hostname != vm.name:
            return InventorySyncStatus.MISMATCH
        return InventorySyncStatus.SYNCED if server.managed else InventorySyncStatus.UNMANAGED

    @staticmethod
    def _server_status_from_vm(status: str) -> Any:
        from backend.app.modules.inventory.models import ServerStatus

        return ServerStatus.ONLINE if status == "running" else ServerStatus.OFFLINE

    @staticmethod
    def _should_apply_detected_ip(
        server: Server,
        vm: ProxmoxVmRead,
        previous_detected_ip: object,
    ) -> bool:
        if not vm.ip_address:
            return False
        return not server.ip_address or server.ip_address == previous_detected_ip

    async def _ensure_unique(
        self,
        *,
        hostname: str | None = None,
        ip_address: str | None = None,
        exclude_id: UUID | None = None,
    ) -> None:
        if hostname:
            existing = await self.repository.get_by_hostname(hostname)
            if existing and existing.id != exclude_id:
                logger.warning("server_validation_failed", hostname=hostname, reason="hostname_exists")
                raise InventoryConflictError("Hostname already exists")

        if ip_address:
            existing = await self.repository.get_by_ip_address(ip_address)
            if existing and existing.id != exclude_id:
                logger.warning("server_validation_failed", ip_address=ip_address, reason="ip_exists")
                raise InventoryConflictError("IP address already exists")

    @classmethod
    def _managed_node_defaults(cls, data: dict[str, Any]) -> dict[str, Any]:
        provider_type = data.get("provider_type")
        provider = str(data.get("provider") or "").lower()
        if not provider_type and provider == "proxmox" and data.get("vmid"):
            provider_type = "qemu"
        elif not provider_type and provider == "proxmox":
            provider_type = "hypervisor"
        elif not provider_type and data.get("vmid"):
            provider_type = "qemu"
        data["node_type"] = data.get("node_type") or cls._node_type_from_provider_type(provider_type)
        data["management_state"] = data.get("management_state") or (
            ManagementState.MANAGED if data.get("managed", True) else ManagementState.UNMANAGED
        )
        data["sync_state"] = data.get("sync_state") or data.get("sync_status") or InventorySyncStatus.UNKNOWN
        data["capabilities"] = data.get("capabilities") or cls._default_capabilities(data)
        return data

    @staticmethod
    def _node_type_from_provider_type(provider_type: object) -> ManagedNodeType:
        normalized = str(provider_type or "").lower()
        if normalized in {"qemu", "vm"}:
            return ManagedNodeType.VM
        if normalized in {"lxc", "ct"}:
            return ManagedNodeType.LXC
        if normalized in {"hypervisor", "node", "host"}:
            return ManagedNodeType.HYPERVISOR
        return ManagedNodeType.PHYSICAL

    @staticmethod
    def _default_capabilities(data: dict[str, Any]) -> list[str]:
        capabilities = ["monitoring"]
        provider = str(data.get("provider") or "").lower()
        provider_type = str(data.get("provider_type") or "").lower()
        if data.get("ssh_username"):
            capabilities.extend(["ssh", "shell", "filesystem", "identity"])
        if provider_type in {"qemu", "lxc", "ct"} or provider == "proxmox":
            capabilities.append("provisioning")
        return sorted(set(capabilities))

    @staticmethod
    def _normalize_management_fields(server: Server) -> None:
        if server.lifecycle_state in {
            InventoryLifecycleState.ARCHIVED,
            InventoryLifecycleState.DECOMMISSIONED,
            InventoryLifecycleState.DELETED,
        }:
            server.managed = False
            server.management_state = ManagementState.RETIRED
            server.sync_status = InventorySyncStatus.ARCHIVED
            server.sync_state = InventorySyncStatus.ARCHIVED
            return
        if server.lifecycle_state == InventoryLifecycleState.UNMANAGED or not server.managed:
            server.managed = False
            server.management_state = ManagementState.UNMANAGED
            server.sync_status = InventorySyncStatus.UNMANAGED
            server.sync_state = InventorySyncStatus.UNMANAGED
            return
        server.managed = True
        server.management_state = ManagementState.MANAGED
        server.sync_state = server.sync_status
