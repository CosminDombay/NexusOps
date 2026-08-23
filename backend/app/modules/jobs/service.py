import asyncio
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.adapters.ssh import SshAdapter
from backend.app.modules.audit.repository import AuditEventRepository
from backend.app.modules.audit.service import AuditService
from backend.app.modules.auth.models import User
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.inventory.models import InventoryLifecycleState
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.jobs.actions import get_action, list_actions
from backend.app.modules.jobs.models import (
    CustomOperationalAction,
    Job,
    JobExecutionEvent,
    JobStatus,
)
from backend.app.modules.jobs.repository import (
    CustomOperationalActionRepository,
    JobExecutionEventRepository,
    JobRepository,
)
from backend.app.modules.jobs.runtime import JobExecutionRuntime
from backend.app.modules.jobs.schemas import (
    BulkExecutionHostResult,
    BulkExecutionRead,
    JobActionExecuteRequest,
    JobBulkExecuteRequest,
    JobExecuteRequest,
    JobRead,
    OperationalActionCreate,
    OperationalActionRead,
    OperationalActionUpdate,
)
from backend.app.modules.orchestration.activity import job_activity_timeline
from backend.app.modules.orchestration.security import (
    CommandPolicyEngine,
    CommandValidationError,
    SafeCommandBuilder,
    redact_sensitive_text,
)
from backend.app.modules.orchestration.semantics import (
    is_job_failure,
    is_job_success,
    orchestration_origin,
    runtime_metadata,
)
from backend.app.modules.orchestration.utils import success_failure_counts

logger = structlog.get_logger(__name__)

DEFAULT_BULK_MAX_PARALLEL = 4


class JobNotFoundError(Exception):
    """Raised when a job cannot be found."""


class JobTargetNotFoundError(Exception):
    """Raised when an execution target is missing from inventory."""


class JobTargetNotManagedError(Exception):
    """Raised when an execution target is not a managed inventory host."""


class OperationalActionNotFoundError(Exception):
    """Raised when a predefined operational action cannot be found."""


class OperationalActionConflictError(Exception):
    """Raised when an operational action id is already in use."""


class BuiltinOperationalActionError(Exception):
    """Raised when trying to mutate a built-in action."""


class JobService:
    """Application service for orchestration job execution and history."""

    def __init__(
        self,
        *,
        job_repository: JobRepository,
        server_repository: ServerRepository,
        ssh_adapter: SshAdapter,
        action_repository: CustomOperationalActionRepository | None = None,
        credential_service: CredentialService | None = None,
        audit_service: AuditService | None = None,
        session_factory: async_sessionmaker | None = None,
    ) -> None:
        self.job_repository = job_repository
        self.server_repository = server_repository
        self.ssh_adapter = ssh_adapter
        self.action_repository = action_repository
        self.credential_service = credential_service
        self.audit_service = audit_service
        self.session_factory = session_factory
        self.command_builder = SafeCommandBuilder(variable_service=None)
        self.command_policy = CommandPolicyEngine()

    async def list_jobs(self, *, target_server_id: UUID | None = None) -> list[JobRead]:
        jobs = (
            await self.job_repository.list_for_target(target_server_id)
            if target_server_id is not None
            else await self.job_repository.list()
        )
        return [await self._to_read(job) for job in jobs]

    async def get_job(self, job_id: UUID) -> JobRead:
        job = await self.job_repository.get_by_id(job_id)
        if job is None:
            raise JobNotFoundError("Job not found")
        return await self._to_read(job)

    async def list_actions(self) -> list[OperationalActionRead]:
        builtin_actions = [
            OperationalActionRead(**action.__dict__, is_builtin=True)
            for action in list_actions()
        ]
        custom_actions = []
        if self.action_repository is not None:
            custom_actions = [
                self._custom_action_to_read(action)
                for action in await self.action_repository.list()
            ]
        custom_ids = {action.id for action in custom_actions}
        return [action for action in builtin_actions if action.id not in custom_ids] + custom_actions

    async def create_action(self, payload: OperationalActionCreate) -> OperationalActionRead:
        if self.action_repository is None:
            raise RuntimeError("Action repository is required")
        if get_action(payload.id) or await self.action_repository.get_by_slug(payload.id, include_deleted=True):
            raise OperationalActionConflictError("Operational action already exists")
        action = await self.action_repository.create(
            CustomOperationalAction(
                slug=payload.id,
                name=payload.name,
                category=payload.category,
                description=payload.description,
                command=payload.command,
                destructive=payload.destructive,
            )
        )
        await self.action_repository.session.commit()
        return self._custom_action_to_read(action)

    async def update_action(self, action_id: str, payload: OperationalActionUpdate) -> OperationalActionRead:
        if get_action(action_id):
            raise BuiltinOperationalActionError("Built-in actions cannot be edited")
        if self.action_repository is None:
            raise RuntimeError("Action repository is required")
        action = await self.action_repository.get_by_slug(action_id)
        if action is None:
            raise OperationalActionNotFoundError("Operational action not found")
        action.name = payload.name
        action.category = payload.category
        action.description = payload.description
        action.command = payload.command
        action.destructive = payload.destructive
        await self.action_repository.session.commit()
        await self.action_repository.session.refresh(action)
        return self._custom_action_to_read(action)

    async def delete_action(self, action_id: str) -> None:
        if get_action(action_id):
            raise BuiltinOperationalActionError("Built-in actions cannot be deleted")
        if self.action_repository is None:
            raise RuntimeError("Action repository is required")
        action = await self.action_repository.get_by_slug(action_id)
        if action is None:
            raise OperationalActionNotFoundError("Operational action not found")
        action.deleted_at = datetime.now(UTC)
        await self.action_repository.session.commit()

    async def execute_action(self, payload: JobActionExecuteRequest) -> JobRead:
        action = get_action(payload.action_id)
        if action is None and self.action_repository is not None:
            action = await self.action_repository.get_by_slug(payload.action_id)
        if action is None:
            raise OperationalActionNotFoundError("Operational action not found")

        return await self.execute(
            JobExecuteRequest(
                target_server_id=payload.target_server_id,
                operation_type=f"action:{payload.action_id}",
                command=action.command,
                credential_ref=payload.credential_ref,
            ),
            allow_destructive_policy=bool(action.destructive),
        )

    async def execute(
        self,
        payload: JobExecuteRequest,
        *,
        initiated_by: User | None = None,
        allow_destructive_policy: bool = False,
    ) -> JobRead:
        self.command_builder.validate_command(
            payload.command,
            source=payload.operation_type,
            allow_shell_operators=True,
        )
        policy = self.command_policy.evaluate(payload.command, allow_destructive=allow_destructive_policy)
        if policy.policy == "denied":
            raise CommandValidationError(f"Command denied by policy: {policy.reason}")
        server = await self.server_repository.get_by_id(payload.target_server_id)
        if server is None:
            raise JobTargetNotFoundError("Target server not found")
        if not server.managed or server.lifecycle_state in {
            InventoryLifecycleState.ARCHIVED,
            InventoryLifecycleState.DECOMMISSIONED,
            InventoryLifecycleState.DELETED,
        }:
            raise JobTargetNotManagedError("Target server is not managed")

        execution_origin = orchestration_origin(payload.operation_type)
        correlation_id = str(uuid4())
        job = Job(
            target_server_id=server.id,
            operation_type=payload.operation_type,
            command=payload.redacted_command or self._sanitize_command(payload.command),
            actual_command=payload.command,
            command_display=payload.redacted_command or self._sanitize_command(payload.command),
            command_policy=policy.policy,
            command_hash=sha256(payload.command.encode("utf-8")).hexdigest(),
            initiated_by_user_id=initiated_by.id if initiated_by and initiated_by.id else None,
            initiated_by_username=initiated_by.username if initiated_by else None,
            status=JobStatus.PENDING,
            execution_origin=execution_origin,
            correlation_id=correlation_id,
            runtime_metadata=runtime_metadata(
                operation_type=payload.operation_type,
                execution_origin=execution_origin,
                correlation_id=correlation_id,
                target_hostname=server.hostname,
                target_server_id=str(server.id),
            ),
        )
        job = await self.job_repository.create(job)
        await JobExecutionEventRepository(self.job_repository.session).create(
            JobExecutionEvent(
                job_id=job.id,
                event_type="job.intent_created",
                created_at=datetime.now(UTC),
                correlation_id=correlation_id,
                metadata_json={
                    "operation_type": payload.operation_type,
                    "target_server_id": str(server.id),
                    "target_hostname": server.hostname,
                    "command_hash": job.command_hash,
                    "command_policy": policy.policy,
                    "initiated_by_user_id": str(initiated_by.id) if initiated_by and initiated_by.id else None,
                    "initiated_by_username": initiated_by.username if initiated_by else None,
                },
            )
        )
        await self.job_repository.session.commit()

        logger.info(
            "job_created",
            job_id=str(job.id),
            target_server_id=str(server.id),
            operation_type=job.operation_type,
            correlation_id=job.correlation_id,
        )

        runtime = JobExecutionRuntime(
            job_repository=self.job_repository,
            ssh_adapter=self.ssh_adapter,
            credential_service=self.credential_service,
            audit_service=self.audit_service,
        )
        job = await runtime.run(job=job, server=server, payload=payload)

        log_completed = logger.error if is_job_failure(job.status) else logger.info
        log_completed(
            "job_completed",
            job_id=str(job.id),
            status=job.status,
            exit_code=job.exit_code,
            correlation_id=job.correlation_id,
        )
        return await self._to_read(job)

    async def execute_bulk(self, payload: JobBulkExecuteRequest) -> BulkExecutionRead:
        semaphore = asyncio.Semaphore(payload.max_parallel or DEFAULT_BULK_MAX_PARALLEL)

        async def run_target(target_server_id: UUID) -> BulkExecutionHostResult:
            try:
                async with semaphore:
                    job = await self._execute_bulk_target(payload, target_server_id)
                return BulkExecutionHostResult(
                    target_server_id=target_server_id,
                    target_hostname=job.target_hostname,
                    success=is_job_success(job.status),
                    job=job,
                    error=job.stderr if is_job_failure(job.status) else None,
                )
            except Exception as exc:
                server = await self.server_repository.get_by_id(target_server_id)
                return BulkExecutionHostResult(
                    target_server_id=target_server_id,
                    target_hostname=server.hostname if server else None,
                    success=False,
                    error=str(exc),
                )

        results = list(await asyncio.gather(*(run_target(target_id) for target_id in payload.target_server_ids)))
        success_count, failure_count = success_failure_counts(results)
        return BulkExecutionRead(
            operation_type=payload.operation_type,
            success_count=success_count,
            failure_count=failure_count,
            results=results,
        )

    async def _execute_bulk_target(self, payload: JobBulkExecuteRequest, target_server_id: UUID) -> JobRead:
        request = JobExecuteRequest(
            target_server_id=target_server_id,
            operation_type=payload.operation_type,
            command=payload.command,
            redacted_command=payload.redacted_command,
            credential_ref=payload.credential_ref,
        )
        if self.session_factory is None:
            return await self.execute(request)
        async with self.session_factory() as session:
            service = JobService(
                job_repository=JobRepository(session),
                server_repository=ServerRepository(session),
                ssh_adapter=self.ssh_adapter,
                action_repository=CustomOperationalActionRepository(session) if self.action_repository is not None else None,
                credential_service=CredentialService(repository=CredentialRepository(session)) if self.credential_service is not None else None,
                audit_service=AuditService(AuditEventRepository(session)) if self.audit_service is not None else None,
                session_factory=self.session_factory,
            )
            return await service.execute(request)

    async def cancel_job(self, job_id: UUID) -> JobRead:
        job = await self.job_repository.get_by_id(job_id)
        if job is None:
            raise JobNotFoundError("Job not found")

        runtime = JobExecutionRuntime(
            job_repository=self.job_repository,
            ssh_adapter=self.ssh_adapter,
            credential_service=self.credential_service,
            audit_service=self.audit_service,
        )
        await runtime.request_cancel(job)

        return await self._to_read(job)

    async def _to_read(self, job: Job) -> JobRead:
        server = await self.server_repository.get_by_id(job.target_server_id)
        data = JobRead.model_validate(job)
        target_hostname = server.hostname if server else None
        return data.model_copy(
            update={
                "target_hostname": target_hostname,
                "activity_timeline": job_activity_timeline(job, target_hostname=target_hostname),
            }
        )

    @staticmethod
    def _custom_action_to_read(action: CustomOperationalAction) -> OperationalActionRead:
        return OperationalActionRead(
            id=action.slug,
            name=action.name,
            category=action.category,
            description=action.description,
            command=action.command,
            destructive=action.destructive,
            is_builtin=False,
        )

    @staticmethod
    def _sanitize_command(command: str) -> str:
        return redact_sensitive_text(command)
