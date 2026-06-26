from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy import delete, inspect, select, update

from backend.app.modules.automations.models import Automation
from backend.app.modules.auth.models import RemoteAccessToken
from backend.app.modules.deployments.models import Deployment, DeploymentRevision, DeploymentStatus, DeploymentTarget, DeploymentTargetExecution
from backend.app.modules.execution.models import CommandExecution
from backend.app.modules.identity.models import IdentityExecution
from backend.app.modules.inventory.models import (
    InventoryLifecycleState,
    InventoryHealthStatus,
    InventorySyncStatus,
    ManagedNodeType,
    ManagementState,
    Server,
    ServerEnvironment,
)
from backend.app.modules.jobs.models import Job
from backend.app.modules.monitoring.models import MetricSample, MonitoringSnapshot, MonitoringValidationAttempt
from backend.app.modules.packages.models import PackageInstallation
from backend.app.modules.provisioning.models import ProvisioningRequest, VirtualMachine
from backend.app.modules.runtime_state.models import NodeRuntimeSnapshot, RuntimeRefreshEvent
from backend.app.modules.workflows.models import WorkflowRun
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.schemas import (
    InventoryCredentialReadinessRead,
    InventoryReadinessSignal,
    ProxmoxInventoryImport,
    ServerCreate,
    ServerUpdate,
)
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
        existing = await self.repository.get_by_provider_external_id_for_integration(
            "proxmox",
            str(payload.vm_id),
            payload.integration_id,
        )
        if existing is None:
            existing = await self.repository.get_by_hostname(payload.hostname)
        if existing is None:
            existing = await self.repository.get_by_ip_address(payload.ip_address)

        if existing:
            if existing.lifecycle_state in {
                InventoryLifecycleState.ARCHIVED,
                InventoryLifecycleState.DECOMMISSIONED,
            }:
                return await self._adopt_existing_proxmox_server(
                    existing,
                    payload=payload,
                    discovered_vm=discovered_vm,
                    adoption_reason="manual_import_restore",
                    metadata_flag="restored_from_archive",
                )
            if existing.lifecycle_state in {
                InventoryLifecycleState.DISCOVERED,
                InventoryLifecycleState.UNMANAGED,
            }:
                return await self._adopt_existing_proxmox_server(
                    existing,
                    payload=payload,
                    discovered_vm=discovered_vm,
                    adoption_reason="manual_import_promote",
                    metadata_flag="promoted_from_discovery",
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
            integration_id=payload.integration_id,
            source_type="proxmox",
            managed=True,
            node_type=self._node_type_from_provider_type(payload.vm_type),
            management_state=ManagementState.MANAGED,
            lifecycle_state=InventoryLifecycleState.MANAGED,
            sync_status=InventorySyncStatus.SYNCED if discovered_vm else InventorySyncStatus.UNKNOWN,
            sync_state=InventorySyncStatus.SYNCED if discovered_vm else InventorySyncStatus.UNKNOWN,
            provider_node=payload.node,
            provider_type=payload.vm_type,
            provider_metadata={
                "integration_id": str(payload.integration_id),
                "vm_name": vm_name,
                "detected_ip_address": discovered_vm.ip_address if discovered_vm else None,
            },
            sync_metadata={
                "source_type": "proxmox",
                "last_sync_reason": "manual_import",
                "provider_node": payload.node,
                "provider_type": payload.vm_type,
            },
            last_seen_at=datetime.now(UTC) if discovered_vm else None,
            last_sync_at=datetime.now(UTC) if discovered_vm else None,
            stale_since=None,
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

    async def _adopt_existing_proxmox_server(
        self,
        server: Server,
        *,
        payload: ProxmoxInventoryImport,
        discovered_vm: ProxmoxVmRead | None,
        adoption_reason: str,
        metadata_flag: str,
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
        server.integration_id = payload.integration_id
        server.source_type = "proxmox"
        server.managed = True
        server.node_type = self._node_type_from_provider_type(payload.vm_type)
        server.management_state = ManagementState.MANAGED
        server.lifecycle_state = InventoryLifecycleState.MANAGED
        server.sync_status = InventorySyncStatus.SYNCED if discovered_vm else InventorySyncStatus.UNKNOWN
        server.sync_state = server.sync_status
        server.provider_node = payload.node
        server.provider_type = payload.vm_type
        server.provider_metadata = {
            "integration_id": str(payload.integration_id),
            "vm_name": vm_name,
            metadata_flag: True,
        }
        if discovered_vm and discovered_vm.ip_address:
            server.provider_metadata["detected_ip_address"] = discovered_vm.ip_address
        server.last_seen_at = datetime.now(UTC) if discovered_vm else None
        server.last_sync_at = server.last_seen_at
        server.stale_since = None
        server.sync_metadata = {
            **server.sync_metadata,
            "source_type": "proxmox",
            "last_sync_reason": adoption_reason,
            "provider_node": payload.node,
            "provider_type": payload.vm_type,
        }

        await self.repository.session.commit()
        await self.repository.session.refresh(server)
        await self.runtime_snapshots.refresh_inventory_snapshot(server)
        logger.info(
            "proxmox_vm_existing_record_adopted",
            server_id=str(server.id),
            vm_id=payload.vm_id,
            hostname=server.hostname,
            adoption_reason=adoption_reason,
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

    async def credential_readiness(self, server_id: UUID) -> InventoryCredentialReadinessRead:
        server = await self.repository.get_by_id(server_id)
        if server is None:
            raise ServerNotFoundError("Server not found")

        signals: list[InventoryReadinessSignal] = []
        managed_active = server.managed and server.lifecycle_state not in {
            InventoryLifecycleState.ARCHIVED,
            InventoryLifecycleState.DECOMMISSIONED,
            InventoryLifecycleState.DELETED,
        }
        signals.append(
            InventoryReadinessSignal(
                key="managed_state",
                label="Managed state",
                status="ready" if managed_active else "blocked",
                detail="Host is eligible for Jobs-backed orchestration." if managed_active else "Host is inactive or unmanaged.",
            )
        )

        has_credential_ref = server.credential_id is not None
        has_inline_password = bool(server.ssh_password)
        has_private_key_path = bool(server.ssh_private_key_path)
        ssh_configured = bool(
            server.ip_address
            and server.ssh_username
            and (
                has_credential_ref
                or has_inline_password
                or has_private_key_path
                or server.ssh_auth_method.value == "key"
            )
        )
        signals.append(
            InventoryReadinessSignal(
                key="ssh",
                label="SSH execution",
                status="ready" if ssh_configured else "blocked",
                detail="SSH host, user, and authentication metadata are configured." if ssh_configured else "SSH connection metadata is incomplete.",
            )
        )
        signals.append(
            InventoryReadinessSignal(
                key="credential_reference",
                label="Credential reference",
                status="ready" if has_credential_ref else "warning",
                detail="Host has a shared credential reference." if has_credential_ref else "Host will rely on inline metadata or explicit execution credentials.",
            )
        )

        sudo_ready = has_credential_ref or has_inline_password
        signals.append(
            InventoryReadinessSignal(
                key="sudo",
                label="Sudo fallback",
                status="ready" if sudo_ready else "warning",
                detail="Password-backed credential material can feed non-interactive sudo." if sudo_ready else "Passwordless sudo or a per-run execution credential is required for privileged commands.",
            )
        )

        docker_known = "docker" in {capability.lower() for capability in (server.capabilities or [])}
        docker_ready = docker_known or sudo_ready
        signals.append(
            InventoryReadinessSignal(
                key="docker",
                label="Docker operations",
                status="ready" if docker_ready else "warning",
                detail="Docker capability or sudo fallback is available for discovery/deployments." if docker_ready else "Docker discovery may fail unless the user has Docker group access.",
            )
        )

        blockers = [signal for signal in signals if signal.status == "blocked"]
        warnings = [signal for signal in signals if signal.status == "warning"]
        overall = "blocked" if blockers else "warning" if warnings else "ready"
        return InventoryCredentialReadinessRead(
            server_id=server.id,
            hostname=server.hostname,
            ssh_ready=managed_active and ssh_configured,
            sudo_ready=sudo_ready,
            docker_ready=docker_ready,
            overall_status=overall,
            signals=signals,
        )

    async def sanitize_proxmox_discovered_guests(self, *, dry_run: bool = False) -> tuple[list[str], list[str]]:
        deleted: list[str] = []
        skipped: list[str] = []

        for server in await self.repository.list_by_provider("proxmox"):
            if server.node_type not in {ManagedNodeType.VM, ManagedNodeType.LXC}:
                continue
            if server.managed:
                skipped.append(f"{server.hostname}: managed")
                continue
            if server.lifecycle_state not in {
                InventoryLifecycleState.DISCOVERED,
                InventoryLifecycleState.UNMANAGED,
            }:
                skipped.append(f"{server.hostname}: lifecycle={server.lifecycle_state.value}")
                continue
            if not self._is_discovered_proxmox_guest_record(server):
                skipped.append(f"{server.hostname}: not discovery-created")
                continue

            if not dry_run:
                await self._cleanup_server_references(server.id)
                await self.repository.delete(server)
            deleted.append(server.hostname)

        if deleted and not dry_run:
            await self.repository.session.commit()

        logger.info(
            "proxmox_discovered_inventory_sanitized",
            dry_run=dry_run,
            deleted_count=len(deleted),
            skipped_count=len(skipped),
        )
        return deleted, skipped

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
        automations = (
            await self.repository.session.execute(
                select(Automation).where(Automation.target_server_ids.contains(str(server_id)))
            )
        ).scalars().all()
        for automation in automations:
            automation.target_server_ids = [
                item for item in automation.target_server_ids if str(item) != str(server_id)
            ]

        job_ids = select(Job.id).where(Job.target_server_id == server_id)
        await self.repository.session.execute(
            update(DeploymentTargetExecution)
            .where(DeploymentTargetExecution.job_id.in_(job_ids))
            .values(job_id=None)
        )
        await self.repository.session.execute(
            update(DeploymentRevision)
            .where(DeploymentRevision.job_id.in_(job_ids))
            .values(job_id=None)
        )
        await self.repository.session.execute(
            update(DeploymentTarget)
            .where(DeploymentTarget.last_job_id.in_(job_ids))
            .values(last_job_id=None)
        )
        await self.repository.session.execute(
            update(IdentityExecution)
            .where(IdentityExecution.job_id.in_(job_ids))
            .values(job_id=None)
        )
        affected_deployment_ids = [
            deployment_id
            for deployment_id in (
                await self.repository.session.execute(
                    select(DeploymentTarget.deployment_id).where(DeploymentTarget.server_id == server_id)
                )
            ).scalars().all()
        ]
        await self.repository.session.execute(
            update(ProvisioningRequest)
            .where(ProvisioningRequest.server_id == server_id)
            .values(server_id=None)
        )
        await self._execute_if_table_exists(
            VirtualMachine.__tablename__,
            update(VirtualMachine)
            .where(VirtualMachine.server_id == server_id)
            .values(server_id=None),
        )
        await self.repository.session.execute(
            update(WorkflowRun)
            .where(WorkflowRun.target_server_id == server_id)
            .values(target_server_id=None)
        )
        await self.repository.session.execute(
            update(RuntimeRefreshEvent)
            .where(RuntimeRefreshEvent.node_id == server_id)
            .values(node_id=None)
        )
        await self.repository.session.execute(delete(DeploymentTargetExecution).where(DeploymentTargetExecution.server_id == server_id))
        await self.repository.session.execute(delete(DeploymentRevision).where(DeploymentRevision.server_id == server_id))
        await self.repository.session.execute(delete(DeploymentTarget).where(DeploymentTarget.server_id == server_id))
        await self.repository.session.execute(delete(IdentityExecution).where(IdentityExecution.target_server_id == server_id))
        await self._execute_if_table_exists(
            PackageInstallation.__tablename__,
            delete(PackageInstallation).where(PackageInstallation.server_id == server_id),
        )
        await self._execute_if_table_exists(
            CommandExecution.__tablename__,
            delete(CommandExecution).where(CommandExecution.server_id == server_id),
        )
        await self.repository.session.execute(delete(MonitoringValidationAttempt).where(MonitoringValidationAttempt.server_id == server_id))
        await self.repository.session.execute(delete(MonitoringSnapshot).where(MonitoringSnapshot.server_id == server_id))
        await self.repository.session.execute(delete(MetricSample).where(MetricSample.server_id == server_id))
        await self.repository.session.execute(delete(NodeRuntimeSnapshot).where(NodeRuntimeSnapshot.node_id == server_id))
        await self.repository.session.execute(delete(RemoteAccessToken).where(RemoteAccessToken.server_id == server_id))
        await self.repository.session.execute(delete(Job).where(Job.target_server_id == server_id))
        if affected_deployment_ids:
            await self.repository.session.execute(
                update(Deployment)
                .where(Deployment.id.in_(affected_deployment_ids))
                .values(status=DeploymentStatus.DRAFT)
            )

    async def _table_exists(self, table_name: str) -> bool:
        connection = await self.repository.session.connection()
        return await connection.run_sync(lambda sync_connection: inspect(sync_connection).has_table(table_name))

    async def _execute_if_table_exists(self, table_name: str, statement: Any) -> None:
        if not await self._table_exists(table_name):
            logger.warning(
                "server_reference_cleanup_skipped_missing_table",
                table_name=table_name,
            )
            return
        await self.repository.session.execute(statement)

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
        integration_id: UUID | None = None,
        cluster: str | None = None,
        search: str | None = None,
        include_inactive: bool = False,
        include_unmanaged: bool = False,
    ) -> list[Server]:
        servers = await self.repository.list(
            environment=environment,
            provider=provider,
            integration_id=integration_id,
            cluster=cluster,
            search=search,
            include_inactive=include_inactive,
            include_unmanaged=include_unmanaged,
        )
        return await self.runtime_snapshots.attach_snapshots(servers)

    async def reconcile_proxmox_inventory(
        self,
        discovered_vms: list[ProxmoxVmRead],
        *,
        integration_id: UUID,
        disconnected: bool = False,
    ) -> list[Server]:
        by_external_id = {str(vm.vm_id): vm for vm in discovered_vms}
        by_hostname = {vm.name: vm for vm in discovered_vms}
        changed: list[Server] = []

        now = datetime.now(UTC)
        for server in await self.repository.list_by_provider_integration("proxmox", integration_id):
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
                server.sync_status = InventorySyncStatus.DISCONNECTED if disconnected else InventorySyncStatus.STALE
                server.sync_state = server.sync_status
                server.stale_since = server.stale_since or now
            else:
                server.external_id = str(vm.vm_id)
                server.vmid = str(vm.vm_id)
                server.provider_node = vm.node
                server.provider_type = vm.type
                server.node_type = self._node_type_from_provider_type(vm.type)
                server.integration_id = integration_id
                server.source_type = "proxmox"
                server.last_seen_at = now
                server.last_sync_at = now
                server.stale_since = None
                previous_detected_ip = server.provider_metadata.get("detected_ip_address")
                server.provider_metadata = {
                    **server.provider_metadata,
                    "integration_id": str(integration_id),
                    "vm_name": vm.name,
                    "vm_status": vm.status,
                    "detected_ip_address": vm.ip_address,
                }
                if self._should_apply_detected_ip(server, vm, previous_detected_ip):
                    server.ip_address = vm.ip_address
                server.sync_status = self._sync_status_for_match(server, vm)
                server.sync_state = server.sync_status
                server.sync_metadata = {
                    **server.sync_metadata,
                    "source_type": "proxmox",
                    "last_sync_reason": "reconcile",
                    "provider_node": vm.node,
                    "provider_type": vm.type,
                }
            changed.append(server)

        if changed:
            await self.runtime_snapshots.refresh_inventory_snapshots(changed, commit=False)
            await self.repository.session.commit()

        return changed

    async def mark_integration_resources_disconnected(
        self,
        integration_id: UUID,
        *,
        error: str | None = None,
    ) -> list[Server]:
        now = datetime.now(UTC)
        changed: list[Server] = []
        for server in await self.repository.list_by_provider_integration("proxmox", integration_id):
            if server.lifecycle_state in {
                InventoryLifecycleState.ARCHIVED,
                InventoryLifecycleState.DECOMMISSIONED,
                InventoryLifecycleState.DELETED,
            }:
                continue
            server.sync_status = InventorySyncStatus.DISCONNECTED
            server.sync_state = InventorySyncStatus.DISCONNECTED
            server.stale_since = server.stale_since or now
            server.sync_metadata = {
                **server.sync_metadata,
                "source_type": "proxmox",
                "last_sync_reason": "integration_disconnected",
                "last_error": error,
                "disconnected_at": now.isoformat(),
            }
            changed.append(server)
        if changed:
            await self.runtime_snapshots.refresh_inventory_snapshots(changed, commit=False)
            await self.repository.session.commit()
        return changed

    @staticmethod
    def match_discovered_vm(
        vm: ProxmoxVmRead,
        inventory: list[Server],
        integration_id: str | None = None,
    ) -> tuple[Server | None, InventorySyncStatus, list[str]]:
        notes: list[str] = []
        match = next(
            (
                server
                for server in inventory
                if server.provider == "proxmox"
                and (integration_id is None or str(server.integration_id) == integration_id)
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

    @staticmethod
    def _is_discovered_proxmox_guest_record(server: Server) -> bool:
        return (
            "discovered" in server.tags
            or server.sync_metadata.get("last_sync_reason") == "guest_sync"
            or server.provider_metadata.get("operational_readiness") is not None
        )

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
        data["source_type"] = data.get("source_type") or data.get("source") or "manual"
        data["sync_state"] = data.get("sync_state") or data.get("sync_status") or InventorySyncStatus.UNKNOWN
        data["sync_metadata"] = data.get("sync_metadata") or {}
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
