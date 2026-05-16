from datetime import UTC, datetime
from uuid import UUID

import structlog

from backend.app.adapters.ssh import SshAdapter
from backend.app.modules.credentials.service import CredentialNotFoundError, CredentialService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.models import InventoryLifecycleState, ServerSshAuthMethod
from backend.app.modules.jobs.actions import get_action, list_actions
from backend.app.modules.jobs.models import Job, JobStatus
from backend.app.modules.jobs.repository import JobRepository
from backend.app.modules.jobs.schemas import (
    BulkExecutionHostResult,
    BulkExecutionRead,
    JobActionExecuteRequest,
    JobBulkExecuteRequest,
    JobExecuteRequest,
    JobRead,
    OperationalActionRead,
)

logger = structlog.get_logger(__name__)


class JobNotFoundError(Exception):
    """Raised when a job cannot be found."""


class JobTargetNotFoundError(Exception):
    """Raised when an execution target is missing from inventory."""


class JobTargetNotManagedError(Exception):
    """Raised when an execution target is not a managed inventory host."""


class OperationalActionNotFoundError(Exception):
    """Raised when a predefined operational action cannot be found."""


class JobService:
    """Application service for orchestration job execution and history."""

    def __init__(
        self,
        *,
        job_repository: JobRepository,
        server_repository: ServerRepository,
        ssh_adapter: SshAdapter,
        credential_service: CredentialService | None = None,
    ) -> None:
        self.job_repository = job_repository
        self.server_repository = server_repository
        self.ssh_adapter = ssh_adapter
        self.credential_service = credential_service

    async def list_jobs(self) -> list[JobRead]:
        jobs = await self.job_repository.list()
        return [await self._to_read(job) for job in jobs]

    async def get_job(self, job_id: UUID) -> JobRead:
        job = await self.job_repository.get_by_id(job_id)
        if job is None:
            raise JobNotFoundError("Job not found")
        return await self._to_read(job)

    async def list_actions(self) -> list[OperationalActionRead]:
        return [OperationalActionRead(**action.__dict__) for action in list_actions()]

    async def execute_action(self, payload: JobActionExecuteRequest) -> JobRead:
        action = get_action(payload.action_id)
        if action is None:
            raise OperationalActionNotFoundError("Operational action not found")

        return await self.execute(
            JobExecuteRequest(
                target_server_id=payload.target_server_id,
                operation_type=f"action:{action.id}",
                command=action.command,
                credential_ref=payload.credential_ref,
            )
        )

    async def execute(self, payload: JobExecuteRequest) -> JobRead:
        server = await self.server_repository.get_by_id(payload.target_server_id)
        if server is None:
            raise JobTargetNotFoundError("Target server not found")
        if not server.managed or server.lifecycle_state == InventoryLifecycleState.ARCHIVED:
            raise JobTargetNotManagedError("Target server is not managed")

        job = Job(
            target_server_id=server.id,
            operation_type=payload.operation_type,
            command=payload.redacted_command or payload.command,
            status=JobStatus.PENDING,
        )
        job = await self.job_repository.create(job)
        await self.job_repository.session.commit()

        logger.info(
            "job_created",
            job_id=str(job.id),
            target_server_id=str(server.id),
            operation_type=job.operation_type,
        )

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(UTC)
        await self.job_repository.session.commit()
        await self.job_repository.session.refresh(job)

        try:
            ssh_user = server.ssh_username
            ssh_password = (
                server.ssh_password if server.ssh_auth_method == ServerSshAuthMethod.PASSWORD else None
            )
            ssh_private_key_path = (
                server.ssh_private_key_path if server.ssh_auth_method == ServerSshAuthMethod.KEY else None
            )
            credential_ref = payload.credential_ref or (str(server.credential_id) if server.credential_id is not None else None)
            if credential_ref:
                if self.credential_service is None:
                    raise CredentialNotFoundError("Credential service is required for credential-backed execution")
                credential = await self.credential_service.resolve_credential(credential_ref)
                ssh_user = credential.username or ssh_user
                if credential.credential_type in {"password", "ssh_password"}:
                    ssh_password = credential.secret
                    ssh_private_key_path = None
                elif credential.credential_type == "ssh_key":
                    ssh_password = None
                    ssh_private_key_path = server.ssh_private_key_path

            result = await self.ssh_adapter.run_command(
                host=server.ip_address,
                port=server.ssh_port,
                command=payload.command,
                user=ssh_user,
                password=ssh_password,
                private_key_path=ssh_private_key_path,
            )
            job.stdout = result.stdout
            job.stderr = result.stderr
            job.exit_code = result.exit_code
            job.status = JobStatus.SUCCESS if result.exit_code == 0 else JobStatus.FAILED
        except Exception as exc:
            job.stdout = ""
            job.stderr = str(exc)
            job.exit_code = None
            job.status = JobStatus.FAILED

        job.completed_at = datetime.now(UTC)
        await self.job_repository.session.commit()
        await self.job_repository.session.refresh(job)

        logger.info(
            "job_completed",
            job_id=str(job.id),
            status=job.status,
            exit_code=job.exit_code,
        )
        return await self._to_read(job)

    async def execute_bulk(self, payload: JobBulkExecuteRequest) -> BulkExecutionRead:
        results: list[BulkExecutionHostResult] = []
        for target_server_id in payload.target_server_ids:
            server = await self.server_repository.get_by_id(target_server_id)
            try:
                job = await self.execute(
                    JobExecuteRequest(
                        target_server_id=target_server_id,
                        operation_type=payload.operation_type,
                        command=payload.command,
                        redacted_command=payload.redacted_command,
                        credential_ref=payload.credential_ref,
                    )
                )
                results.append(
                    BulkExecutionHostResult(
                        target_server_id=target_server_id,
                        target_hostname=job.target_hostname,
                        success=job.status == JobStatus.SUCCESS,
                        job=job,
                        error=job.stderr if job.status == JobStatus.FAILED else None,
                    )
                )
            except Exception as exc:
                results.append(
                    BulkExecutionHostResult(
                        target_server_id=target_server_id,
                        target_hostname=server.hostname if server else None,
                        success=False,
                        error=str(exc),
                    )
                )

        success_count = sum(1 for result in results if result.success)
        return BulkExecutionRead(
            operation_type=payload.operation_type,
            success_count=success_count,
            failure_count=len(results) - success_count,
            results=results,
        )

    async def cancel_job(self, job_id: UUID) -> JobRead:
        job = await self.job_repository.get_by_id(job_id)
        if job is None:
            raise JobNotFoundError("Job not found")

        if job.status in {JobStatus.PENDING, JobStatus.RUNNING}:
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now(UTC)
            await self.job_repository.session.commit()
            await self.job_repository.session.refresh(job)

        return await self._to_read(job)

    async def _to_read(self, job: Job) -> JobRead:
        server = await self.server_repository.get_by_id(job.target_server_id)
        data = JobRead.model_validate(job)
        return data.model_copy(update={"target_hostname": server.hostname if server else None})
