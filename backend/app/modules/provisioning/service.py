import asyncio
from ipaddress import ip_interface
from uuid import UUID

import structlog

from backend.app.adapters.proxmox import ProxmoxAdapter
from backend.app.adapters.ssh import SshAdapter
from backend.app.modules.inventory.models import ServerSshAuthMethod, ServerStatus
from backend.app.modules.inventory.repository import ServerRepository
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
from backend.app.modules.provisioning.models import ProvisioningRequest, ProvisioningStatus
from backend.app.modules.provisioning.repository import ProvisioningRequestRepository
from backend.app.modules.provisioning.schemas import (
    ProxmoxTemplateRead,
    ProvisioningCreate,
    ProvisioningRead,
)

logger = structlog.get_logger(__name__)


class ProvisioningNotFoundError(Exception):
    """Raised when a provisioning request cannot be found."""


class ProvisioningValidationError(Exception):
    """Raised when provisioning input is invalid for current state."""


class ProvisioningService:
    """Application service for template-based Proxmox VM provisioning."""

    def __init__(
        self,
        *,
        repository: ProvisioningRequestRepository,
        server_repository: ServerRepository,
        job_repository: JobRepository,
        package_repository: PackageDefinitionRepository,
        profile_repository: InfrastructureProfileRepository,
        proxmox_adapter: ProxmoxAdapter,
        ssh_adapter: SshAdapter,
    ) -> None:
        self.repository = repository
        self.server_repository = server_repository
        self.job_repository = job_repository
        self.package_repository = package_repository
        self.profile_repository = profile_repository
        self.proxmox_adapter = proxmox_adapter
        self.ssh_adapter = ssh_adapter

    async def list_requests(self) -> list[ProvisioningRead]:
        return [ProvisioningRead.model_validate(item) for item in await self.repository.list()]

    async def get_request(self, request_id: UUID) -> ProvisioningRead:
        request = await self.repository.get_by_id(request_id)
        if request is None:
            raise ProvisioningNotFoundError("Provisioning request not found")
        return ProvisioningRead.model_validate(request)

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

    async def provision(self, payload: ProvisioningCreate) -> ProvisioningRead:
        static_ip = str(ip_interface(payload.static_ip_cidr).ip)
        request = ProvisioningRequest(
            vm_name=payload.vm_name,
            target_node=payload.target_node,
            template_id=payload.template_id,
            new_vm_id=payload.new_vm_id,
            cpu_cores=payload.cpu_cores,
            memory_mb=payload.memory_mb,
            disk_gb=payload.disk_gb,
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
        )
        request = await self.repository.create(request)
        await self.repository.session.commit()
        await self.repository.session.refresh(request)

        try:
            await self._set_status(request, ProvisioningStatus.VALIDATING_IP)
            if await self.server_repository.get_by_ip_address(static_ip):
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
            server = await InventoryService(self.server_repository).create_server(
                ServerCreate(
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
                )
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
        )
        profile_service = ProfileService(
            job_service=job_service,
            repository=self.profile_repository,
            package_repository=self.package_repository,
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

    pass
