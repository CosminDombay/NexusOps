from datetime import UTC, datetime
from uuid import UUID

import structlog

from backend.app.adapters.ssh import SshAdapter
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.models import ServerSshAuthMethod
from backend.app.modules.jobs.actions import get_action, list_actions
from backend.app.modules.jobs.models import Job, JobStatus
from backend.app.modules.jobs.repository import JobRepository
from backend.app.modules.jobs.schemas import (
    JobActionExecuteRequest,
    JobExecuteRequest,
    JobRead,
    OperationalActionRead,
)

logger = structlog.get_logger(__name__)


class JobNotFoundError(Exception):
    """Raised when a job cannot be found."""


class JobTargetNotFoundError(Exception):
    """Raised when an execution target is missing from inventory."""


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
    ) -> None:
        self.job_repository = job_repository
        self.server_repository = server_repository
        self.ssh_adapter = ssh_adapter

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
            )
        )

    async def execute(self, payload: JobExecuteRequest) -> JobRead:
        server = await self.server_repository.get_by_id(payload.target_server_id)
        if server is None:
            raise JobTargetNotFoundError("Target server not found")

        job = Job(
            target_server_id=server.id,
            operation_type=payload.operation_type,
            command=payload.command,
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
            result = await self.ssh_adapter.run_command(
                host=server.ip_address,
                port=server.ssh_port,
                command=payload.command,
                user=server.ssh_username,
                password=server.ssh_password
                if server.ssh_auth_method == ServerSshAuthMethod.PASSWORD
                else None,
                private_key_path=server.ssh_private_key_path
                if server.ssh_auth_method == ServerSshAuthMethod.KEY
                else None,
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
