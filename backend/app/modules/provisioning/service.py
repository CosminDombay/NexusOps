import asyncio
from ipaddress import ip_address, ip_interface
from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError

from backend.app.adapters.proxmox import ProxmoxAdapter
from backend.app.adapters.ssh import SshAdapter
from backend.app.common.constants import (
    InventoryLifecycleState,
    InventorySyncStatus,
    ServerEnvironment,
    ServerSshAuthMethod,
    ServerStatus,
)
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.deployments.repository import (
    DeploymentRepository,
    DeploymentRevisionRepository,
    DeploymentTargetRepository,
)
from backend.app.modules.deployments.service import DockerComposeDeploymentService
from backend.app.modules.inventory.schemas import ServerCreate
from backend.app.modules.inventory.service import InventoryConflictError, InventoryService
from backend.app.modules.jobs.repository import JobRepository
from backend.app.modules.jobs.service import JobService
from backend.app.modules.packages.repository import PackageDefinitionRepository
from backend.app.modules.packages.schemas import PackageExecuteRequest
from backend.app.modules.packages.service import PackageAutomationService
from backend.app.modules.profiles.repository import InfrastructureProfileRepository
from backend.app.modules.profiles.schemas import ProfileApplyRequest
from backend.app.modules.profiles.service import ProfileService
from backend.app.modules.provisioning.models import (
    ProvisioningBlueprint,
    ProvisioningBatch,
    ProvisioningBatchStatus,
    ProvisioningRequest,
    ProvisioningStatus,
)
from backend.app.modules.provisioning.repository import (
    ProvisioningBlueprintRepository,
    ProvisioningBatchRepository,
    ProvisioningRequestRepository,
)
from backend.app.modules.provisioning.schemas import (
    ProxmoxTemplateRead,
    ProvisioningBlueprintCreate,
    ProvisioningBlueprintRead,
    ProvisioningBlueprintUpdate,
    ProvisioningBatchCreate,
    ProvisioningBatchRead,
    ProvisioningCreate,
    ProvisioningRead,
)

logger = structlog.get_logger(__name__)


class ProvisioningNotFoundError(Exception):
    """Raised when a provisioning request cannot be found."""


class ProvisioningValidationError(Exception):
    """Raised when provisioning input is invalid for current state."""


class ProvisioningBlueprintNotFoundError(Exception):
    """Raised when a provisioning blueprint cannot be found."""


class ProvisioningBlueprintConflictError(Exception):
    """Raised when a provisioning blueprint name already exists."""


class ProvisioningBatchNotFoundError(Exception):
    """Raised when a provisioning batch cannot be found."""


class ProvisioningService:
    """Application service for template-based Proxmox VM provisioning."""

    def __init__(
        self,
        *,
        repository: ProvisioningRequestRepository,
        blueprint_repository: ProvisioningBlueprintRepository,
        batch_repository: ProvisioningBatchRepository,
        server_repository: ServerRepository,
        job_repository: JobRepository,
        package_repository: PackageDefinitionRepository,
        profile_repository: InfrastructureProfileRepository,
        credential_service: CredentialService | None = None,
        proxmox_adapter: ProxmoxAdapter,
        ssh_adapter: SshAdapter,
    ) -> None:
        self.repository = repository
        self.blueprint_repository = blueprint_repository
        self.batch_repository = batch_repository
        self.server_repository = server_repository
        self.job_repository = job_repository
        self.package_repository = package_repository
        self.profile_repository = profile_repository
        self.credential_service = credential_service
        self.proxmox_adapter = proxmox_adapter
        self.ssh_adapter = ssh_adapter

    async def list_requests(self) -> list[ProvisioningRead]:
        return [ProvisioningRead.model_validate(item) for item in await self.repository.list()]

    async def get_request(self, request_id: UUID) -> ProvisioningRead:
        request = await self.repository.get_by_id(request_id)
        if request is None:
            raise ProvisioningNotFoundError("Provisioning request not found")
        return ProvisioningRead.model_validate(request)

    async def delete_request(self, request_id: UUID) -> None:
        request = await self.repository.get_by_id(request_id)
        if request is None:
            raise ProvisioningNotFoundError("Provisioning request not found")
        await self.repository.delete(request)
        await self.repository.session.commit()

    async def list_batches(self) -> list[ProvisioningBatchRead]:
        batches = await self.batch_repository.list()
        return [await self._batch_read(batch) for batch in batches]

    async def get_batch(self, batch_id: UUID) -> ProvisioningBatchRead:
        batch = await self.batch_repository.get_by_id(batch_id)
        if batch is None:
            raise ProvisioningBatchNotFoundError("Provisioning batch not found")
        return await self._batch_read(batch)

    async def list_templates(self) -> list[ProxmoxTemplateRead]:
        templates = await self.proxmox_adapter.list_vm_templates()
        return [
            ProxmoxTemplateRead(
                template_id=int(template.get("vmid")),
                name=str(template.get("name") or template.get("id") or template.get("vmid")),
                node=str(template.get("node")),
                type=str(template.get("type", "qemu")),
            )
            for template in templates
            if template.get("vmid") and template.get("node")
        ]

    async def list_blueprints(self) -> list[ProvisioningBlueprintRead]:
        return [
            ProvisioningBlueprintRead.model_validate(item)
            for item in await self.blueprint_repository.list()
        ]

    async def create_blueprint(
        self,
        payload: ProvisioningBlueprintCreate,
    ) -> ProvisioningBlueprintRead:
        blueprint = ProvisioningBlueprint(**self._blueprint_data(payload))
        try:
            blueprint = await self.blueprint_repository.create(blueprint)
            await self.blueprint_repository.session.commit()
        except IntegrityError as exc:
            await self.blueprint_repository.session.rollback()
            raise ProvisioningBlueprintConflictError("Provisioning blueprint already exists") from exc
        return ProvisioningBlueprintRead.model_validate(blueprint)

    async def update_blueprint(
        self,
        blueprint_id: UUID,
        payload: ProvisioningBlueprintUpdate,
    ) -> ProvisioningBlueprintRead:
        blueprint = await self.blueprint_repository.get_by_id(blueprint_id)
        if blueprint is None:
            raise ProvisioningBlueprintNotFoundError("Provisioning blueprint not found")

        for key, value in self._blueprint_data(payload, exclude_unset=True).items():
            setattr(blueprint, key, value)
        try:
            await self.blueprint_repository.session.commit()
            await self.blueprint_repository.session.refresh(blueprint)
        except IntegrityError as exc:
            await self.blueprint_repository.session.rollback()
            raise ProvisioningBlueprintConflictError("Provisioning blueprint already exists") from exc
        return ProvisioningBlueprintRead.model_validate(blueprint)

    async def delete_blueprint(self, blueprint_id: UUID) -> None:
        blueprint = await self.blueprint_repository.get_by_id(blueprint_id)
        if blueprint is None:
            raise ProvisioningBlueprintNotFoundError("Provisioning blueprint not found")
        await self.blueprint_repository.delete(blueprint)
        await self.blueprint_repository.session.commit()

    async def provision(
        self,
        payload: ProvisioningCreate,
        *,
        batch_id: UUID | None = None,
        batch_index: int | None = None,
    ) -> ProvisioningRead:
        static_ip = str(ip_interface(payload.static_ip_cidr).ip)
        request = ProvisioningRequest(
            vm_name=payload.vm_name,
            target_node=payload.target_node,
            template_id=payload.template_id,
            new_vm_id=payload.new_vm_id,
            cpu_cores=payload.cpu_cores,
            memory_mb=payload.memory_mb,
            disk_gb=payload.disk_gb,
            additional_disks=[disk.model_dump() for disk in payload.additional_disks],
            network_bridge=payload.network_bridge,
            environment=payload.environment.value,
            tags=payload.tags,
            description=payload.description,
            start_on_boot=payload.start_on_boot,
            cloud_init_username=payload.cloud_init_username,
            cloud_init_password=payload.cloud_init_password,
            ssh_public_key=payload.ssh_public_key,
            static_ip_cidr=payload.static_ip_cidr,
            gateway=payload.gateway,
            dns_servers=payload.dns_servers,
            bootstrap_profile_ids=payload.bootstrap_profile_ids,
            bootstrap_package_ids=payload.bootstrap_package_ids,
            status=ProvisioningStatus.REQUESTED,
            batch_id=batch_id,
            batch_index=batch_index,
        )
        request = await self.repository.create(request)
        await self.repository.session.commit()
        await self.repository.session.refresh(request)

        try:
            await self._set_status(request, ProvisioningStatus.VALIDATING_IP)
            archived_inventory = await self._archived_inventory_candidate(
                hostname=payload.cloud_init_hostname,
                ip_address=static_ip,
            )
            if archived_inventory is None:
                if await self._active_inventory_exists(hostname=payload.cloud_init_hostname, ip_address=static_ip):
                    raise ProvisioningValidationError("Requested static IP or hostname already exists in inventory")
            else:
                active_hostname = await self.server_repository.get_by_hostname(payload.cloud_init_hostname)
                if active_hostname and active_hostname.id != archived_inventory.id:
                    raise ProvisioningValidationError("Requested hostname already exists in inventory")
                active_ip = await self.server_repository.get_by_ip_address(static_ip)
                if active_ip and active_ip.id != archived_inventory.id:
                    raise ProvisioningValidationError("Requested static IP already exists in inventory")

            if await self.server_repository.get_by_ip_address(static_ip) and archived_inventory is None:
                raise ProvisioningValidationError("Requested static IP already exists in inventory")

            await self._set_status(request, ProvisioningStatus.CLONING)
            clone_task = await self.proxmox_adapter.clone_vm_template(
                node=payload.target_node,
                template_id=payload.template_id,
                new_vm_id=payload.new_vm_id,
                name=payload.vm_name,
                description=payload.description,
            )
            self._append_task(request, clone_task.get("task_id"))
            await self._wait_for_proxmox_task(payload.target_node, clone_task.get("task_id"))

            await self._set_status(request, ProvisioningStatus.CONFIGURING)
            config_task = await self.proxmox_adapter.configure_cloud_init(
                node=payload.target_node,
                vm_id=payload.new_vm_id,
                cpu_cores=payload.cpu_cores,
                memory_mb=payload.memory_mb,
                network_bridge=payload.network_bridge,
                username=payload.cloud_init_username,
                password=payload.cloud_init_password,
                ssh_public_key=payload.ssh_public_key,
                ip_cidr=payload.static_ip_cidr,
                gateway=payload.gateway,
                dns_servers=payload.dns_servers,
                start_on_boot=payload.start_on_boot,
                description=payload.description,
            )
            self._append_task(request, config_task.get("task_id"))
            await self._wait_for_proxmox_task(payload.target_node, config_task.get("task_id"))
            resize_task = await self.proxmox_adapter.resize_vm_disk(
                node=payload.target_node,
                vm_id=payload.new_vm_id,
                disk_size_gb=payload.disk_gb,
            )
            self._append_task(request, resize_task.get("task_id"))
            await self._wait_for_proxmox_task(payload.target_node, resize_task.get("task_id"))
            for disk_index, disk in enumerate(payload.additional_disks, start=1):
                add_disk_task = await self.proxmox_adapter.add_vm_disk(
                    node=payload.target_node,
                    vm_id=payload.new_vm_id,
                    disk=f"{disk.bus}{disk_index}",
                    storage=disk.storage,
                    size_gb=disk.size_gb,
                )
                self._append_task(request, add_disk_task.get("task_id"))
                await self._wait_for_proxmox_task(payload.target_node, add_disk_task.get("task_id"))
            await self.repository.session.commit()

            await self._set_status(request, ProvisioningStatus.STARTING)
            start_task = await self.proxmox_adapter.start_vm(
                node=payload.target_node,
                vm_id=payload.new_vm_id,
                vm_type="qemu",
            )
            self._append_task(request, start_task.get("task_id"))
            await self._wait_for_proxmox_task(payload.target_node, start_task.get("task_id"))
            await self.repository.session.commit()

            await self._set_status(request, ProvisioningStatus.WAITING_FOR_SSH)
            await self._wait_for_ssh(
                host=static_ip,
                port=22,
                username=payload.cloud_init_username,
                password=payload.cloud_init_password,
            )

            await self._set_status(request, ProvisioningStatus.INVENTORY_REGISTRATION)
            server_payload = ServerCreate(
                hostname=payload.cloud_init_hostname,
                ip_address=static_ip,
                operating_system="cloud-init Linux",
                vmid=str(payload.new_vm_id),
                environment=payload.environment,
                tags=[*payload.tags, "source:provisioned", "managed"],
                ssh_port=22,
                ssh_username=payload.cloud_init_username,
                ssh_auth_method=ServerSshAuthMethod.PASSWORD
                if payload.cloud_init_password
                else ServerSshAuthMethod.KEY,
                ssh_password=payload.cloud_init_password,
                status=ServerStatus.ONLINE,
                provider="proxmox",
                external_id=str(payload.new_vm_id),
                source="provisioned",
                managed=True,
                lifecycle_state=InventoryLifecycleState.PROVISIONED,
                sync_status=InventorySyncStatus.SYNCED,
                provider_node=payload.target_node,
                provider_type="qemu",
                provider_metadata={
                    "template_id": payload.template_id,
                    "vm_name": payload.vm_name,
                    "additional_disks": [disk.model_dump() for disk in payload.additional_disks],
                },
            )
            server = (
                await self._restore_archived_inventory(archived_inventory, server_payload)
                if archived_inventory
                else await InventoryService(self.server_repository).create_server(server_payload)
            )
            request.server_id = server.id
            await self.repository.session.commit()

            if payload.bootstrap_profile_ids or payload.bootstrap_package_ids:
                await self._set_status(request, ProvisioningStatus.BOOTSTRAP_RUNNING)
                await self._run_bootstrap(request)

            await self._set_status(request, ProvisioningStatus.COMPLETED)
        except Exception as exc:
            request.error_message = str(exc)
            request.status = ProvisioningStatus.FAILED
            await self.repository.session.commit()
            logger.warning("provisioning_failed", request_id=str(request.id), reason=str(exc))

        await self.repository.session.refresh(request)
        return ProvisioningRead.model_validate(request)

    async def _active_inventory_exists(self, *, hostname: str, ip_address: str) -> bool:
        for server in (
            await self.server_repository.get_by_hostname(hostname),
            await self.server_repository.get_by_ip_address(ip_address),
        ):
            if server and server.lifecycle_state not in {
                InventoryLifecycleState.ARCHIVED,
                InventoryLifecycleState.DECOMMISSIONED,
                InventoryLifecycleState.DELETED,
            }:
                return True
        return False

    async def _archived_inventory_candidate(self, *, hostname: str, ip_address: str):
        ip_match = await self.server_repository.get_by_ip_address(ip_address)
        hostname_match = await self.server_repository.get_by_hostname(hostname)
        candidates = [
            server
            for server in (ip_match, hostname_match)
            if server
            and server.lifecycle_state in {
                InventoryLifecycleState.ARCHIVED,
                InventoryLifecycleState.DECOMMISSIONED,
            }
        ]
        if not candidates:
            return None
        candidate = candidates[0]
        if any(server.id != candidate.id for server in candidates):
            raise ProvisioningValidationError("Requested static IP and hostname belong to different archived inventory records")
        return candidate

    async def _restore_archived_inventory(self, server, payload: ServerCreate):
        for key, value in payload.model_dump().items():
            setattr(server, key, value)
        await self.server_repository.session.commit()
        await self.server_repository.session.refresh(server)
        return server

    async def provision_batch(self, payload: ProvisioningBatchCreate) -> ProvisioningBatchRead:
        blueprint = await self.blueprint_repository.get_by_id(payload.blueprint_id)
        if blueprint is None:
            raise ProvisioningBlueprintNotFoundError("Provisioning blueprint not found")

        batch = ProvisioningBatch(
            name=payload.name,
            blueprint_id=payload.blueprint_id,
            count=payload.count,
            vm_name_pattern=payload.vm_name_pattern,
            hostname_pattern=payload.hostname_pattern or payload.vm_name_pattern,
            starting_vm_id=payload.starting_vm_id,
            starting_ip_cidr=payload.starting_ip_cidr,
            status=ProvisioningBatchStatus.REQUESTED,
            completed_count=0,
            failed_count=0,
        )
        batch = await self.batch_repository.create(batch)
        await self.batch_repository.session.commit()
        await self.batch_repository.session.refresh(batch)

        batch.status = ProvisioningBatchStatus.RUNNING
        await self.batch_repository.session.commit()

        completed = 0
        failed = 0
        errors: list[str] = []
        start_interface = ip_interface(payload.starting_ip_cidr)
        network = start_interface.network

        for index in range(payload.count):
            number = index + 1
            next_ip = ip_address(int(start_interface.ip) + index)
            if next_ip not in network:
                failed += 1
                errors.append(f"Batch IP range exceeded network at item {number}")
                continue

            vm_id = payload.starting_vm_id + index
            vm_name = self._render_batch_pattern(payload.vm_name_pattern, number)
            hostname = self._render_batch_pattern(payload.hostname_pattern or payload.vm_name_pattern, number)
            child_payload = ProvisioningCreate(
                vm_name=vm_name,
                target_node=blueprint.target_node,
                template_id=blueprint.template_id,
                new_vm_id=vm_id,
                cpu_cores=blueprint.cpu_cores,
                memory_mb=blueprint.memory_mb,
                disk_gb=blueprint.disk_gb,
                additional_disks=blueprint.additional_disks,
                network_bridge=blueprint.network_bridge,
                environment=ServerEnvironment(blueprint.environment),
                tags=[*blueprint.tags, f"batch:{batch.name}"],
                description=payload.description or blueprint.description,
                start_on_boot=blueprint.start_on_boot,
                cloud_init_hostname=hostname,
                cloud_init_username=blueprint.cloud_init_username,
                cloud_init_password=payload.cloud_init_password,
                ssh_public_key=blueprint.ssh_public_key,
                static_ip_cidr=f"{next_ip}/{start_interface.network.prefixlen}",
                gateway=blueprint.gateway,
                dns_servers=blueprint.dns_servers,
                bootstrap_profile_ids=blueprint.bootstrap_profile_ids,
                bootstrap_package_ids=blueprint.bootstrap_package_ids,
            )
            result = await self.provision(child_payload, batch_id=batch.id, batch_index=number)
            if result.status == ProvisioningStatus.COMPLETED:
                completed += 1
            else:
                failed += 1
                if result.error_message:
                    errors.append(f"{vm_name}: {result.error_message}")

            batch.completed_count = completed
            batch.failed_count = failed
            batch.error_message = "\n".join(errors) or None
            await self.batch_repository.session.commit()

        if completed == payload.count:
            batch.status = ProvisioningBatchStatus.COMPLETED
        elif completed > 0:
            batch.status = ProvisioningBatchStatus.PARTIAL_FAILED
        else:
            batch.status = ProvisioningBatchStatus.FAILED
        batch.completed_count = completed
        batch.failed_count = failed
        batch.error_message = "\n".join(errors) or None
        await self.batch_repository.session.commit()
        await self.batch_repository.session.refresh(batch)
        return await self._batch_read(batch)

    @staticmethod
    def _blueprint_data(
        payload: ProvisioningBlueprintCreate | ProvisioningBlueprintUpdate,
        *,
        exclude_unset: bool = False,
    ) -> dict:
        data = payload.model_dump(exclude_unset=exclude_unset)
        if "environment" in data and data["environment"] is not None:
            data["environment"] = data["environment"].value
        return data

    async def _set_status(
        self,
        request: ProvisioningRequest,
        status: ProvisioningStatus,
    ) -> None:
        request.status = status
        await self.repository.session.commit()
        await self.repository.session.refresh(request)

    def _append_task(self, request: ProvisioningRequest, task_id: object) -> None:
        if task_id is not None:
            request.proxmox_task_ids = [*request.proxmox_task_ids, str(task_id)]

    async def _wait_for_ssh(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str | None,
    ) -> None:
        last_error: Exception | None = None
        for _ in range(6):
            try:
                await self.ssh_adapter.run_command(
                    host=host,
                    port=port,
                    user=username,
                    password=password,
                    command="true",
                )
                return
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(5)
        raise ProvisioningValidationError(f"SSH did not become ready: {last_error}")

    async def _wait_for_proxmox_task(self, node: str, task_id: object) -> None:
        if not task_id:
            return
        task_id_str = str(task_id)
        for _ in range(30):
            status = await self.proxmox_adapter.get_task_status(node=node, task_id=task_id_str)
            if status.get("status") == "stopped":
                exit_status = status.get("exitstatus")
                if exit_status in {None, "OK"}:
                    return
                raise ProvisioningValidationError(
                    f"Proxmox task failed: {task_id_str} ({exit_status})"
                )
            await asyncio.sleep(2)
        raise ProvisioningValidationError(f"Timed out waiting for Proxmox task: {task_id_str}")

    async def _run_bootstrap(self, request: ProvisioningRequest) -> None:
        if request.server_id is None:
            raise ProvisioningValidationError("Cannot bootstrap before inventory registration")

        job_service = JobService(
            job_repository=self.job_repository,
            server_repository=self.server_repository,
            ssh_adapter=self.ssh_adapter,
            credential_service=self.credential_service,
        )
        profile_service = ProfileService(
            job_service=job_service,
            repository=self.profile_repository,
            package_repository=self.package_repository,
            deployment_service=DockerComposeDeploymentService(
                repository=DeploymentRepository(self.repository.session),
                target_repository=DeploymentTargetRepository(self.repository.session),
                revision_repository=DeploymentRevisionRepository(self.repository.session),
                server_repository=self.server_repository,
                job_service=job_service,
                credential_service=self.credential_service,
            ),
        )
        package_service = PackageAutomationService(
            repository=self.package_repository,
            job_service=job_service,
        )

        job_ids = list(request.bootstrap_job_ids)
        for profile_id in request.bootstrap_profile_ids:
            result = await profile_service.apply_profile(
                profile_id,
                ProfileApplyRequest(target_server_id=request.server_id),
            )
            job_ids.extend(str(job.id) for job in result.jobs)

        for package_id in request.bootstrap_package_ids:
            job = await package_service.execute_definition(
                package_id,
                PackageExecuteRequest(target_server_id=request.server_id),
            )
            job_ids.append(str(job.id))

        request.bootstrap_job_ids = job_ids
        await self.repository.session.commit()

    async def _batch_read(self, batch: ProvisioningBatch) -> ProvisioningBatchRead:
        requests = await self.repository.list_by_batch(batch.id)
        return ProvisioningBatchRead(
            **{
                **ProvisioningBatchRead.model_validate(batch).model_dump(exclude={"requests"}),
                "requests": [ProvisioningRead.model_validate(request) for request in requests],
            }
        )

    @staticmethod
    def _render_batch_pattern(pattern: str, number: int) -> str:
        return pattern.replace("{index}", f"{number:03d}").replace("{number}", str(number))
