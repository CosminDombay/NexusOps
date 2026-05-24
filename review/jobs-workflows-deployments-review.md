# NexusOps Jobs, Workflows, Deployments Review Bundle

This file contains the requested source code with each original path shown directly above its code block.

## backend/app/modules/jobs/runtime.py

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.app.adapters.ssh import SshAdapter
from backend.app.modules.audit.service import AuditService
from backend.app.modules.credentials.service import CredentialNotFoundError, CredentialService
from backend.app.modules.inventory.models import ServerSshAuthMethod
from backend.app.modules.jobs.models import Job, JobStatus
from backend.app.modules.jobs.repository import JobRepository
from backend.app.modules.jobs.schemas import JobExecuteRequest
from backend.app.modules.orchestration.utils import duration_seconds


TERMINAL_JOB_STATES = {
    JobStatus.COMPLETED,
    JobStatus.SUCCESS,
    JobStatus.FAILED,
    JobStatus.CANCELLED,
    JobStatus.STALE,
}

VALID_JOB_TRANSITIONS = {
    JobStatus.PENDING: {JobStatus.QUEUED, JobStatus.CANCELLED, JobStatus.STALE},
    JobStatus.QUEUED: {JobStatus.DISPATCHED, JobStatus.CANCELLED, JobStatus.STALE},
    JobStatus.DISPATCHED: {JobStatus.RUNNING, JobStatus.CANCELLED, JobStatus.STALE},
    JobStatus.RUNNING: {JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.COMPLETED, JobStatus.CANCELLED, JobStatus.STALE},
    JobStatus.COMPLETED: set(),
    JobStatus.SUCCESS: set(),
    JobStatus.FAILED: set(),
    JobStatus.CANCELLED: set(),
    JobStatus.STALE: set(),
}


class InvalidJobStateTransitionError(Exception):
    """Raised when a job state transition violates the execution state machine."""


@dataclass(frozen=True)
class ExecutionCancellationIntent:
    job_id: UUID
    requested_at: datetime
    reason: str = "cancel_requested"


class ExecutionCancellationRegistry:
    """In-process cancellation intent registry for currently owned runtime work."""

    def __init__(self) -> None:
        self._intents: dict[UUID, ExecutionCancellationIntent] = {}

    def request(self, job_id: UUID, *, reason: str = "cancel_requested") -> ExecutionCancellationIntent:
        intent = ExecutionCancellationIntent(job_id=job_id, requested_at=datetime.now(UTC), reason=reason)
        self._intents[job_id] = intent
        return intent

    def get(self, job_id: UUID) -> ExecutionCancellationIntent | None:
        return self._intents.get(job_id)

    def clear(self, job_id: UUID) -> None:
        self._intents.pop(job_id, None)


class JobExecutionRuntime:
    """Coordinates job execution lifecycle, runtime metadata, and transport calls."""

    def __init__(
        self,
        *,
        job_repository: JobRepository,
        ssh_adapter: SshAdapter,
        credential_service: CredentialService | None = None,
        audit_service: AuditService | None = None,
        cancellation_registry: ExecutionCancellationRegistry | None = None,
    ) -> None:
        self.job_repository = job_repository
        self.ssh_adapter = ssh_adapter
        self.credential_service = credential_service
        self.audit_service = audit_service
        self.cancellation_registry = cancellation_registry or execution_cancellations

    async def run(self, *, job: Job, server, payload: JobExecuteRequest) -> Job:
        correlation_id = job.correlation_id or str(uuid4())
        job.correlation_id = correlation_id
        job.execution_origin = job.execution_origin or self._origin(payload.operation_type)
        job.runtime_metadata = {
            **(job.runtime_metadata or {}),
            "transport": self.ssh_adapter.name,
            "target_hostname": server.hostname,
            "target_server_id": str(server.id),
            "operation_type": payload.operation_type,
        }
        await self.transition(job, JobStatus.QUEUED)
        await self.transition(job, JobStatus.DISPATCHED)
        if await self._cancelled(job):
            return job
        await self.transition(job, JobStatus.RUNNING)

        started = job.started_at or datetime.now(UTC)
        try:
            ssh_user, ssh_password, ssh_private_key_path, ssh_private_key, ssh_passphrase = await self._credentials(server, payload)
            result = await self.ssh_adapter.run_command(
                host=server.ip_address,
                port=server.ssh_port,
                command=payload.command,
                user=ssh_user,
                password=ssh_password,
                private_key_path=ssh_private_key_path,
                private_key=ssh_private_key,
                passphrase=ssh_passphrase,
            )
            job.stdout = result.stdout
            job.stderr = result.stderr
            job.exit_code = result.exit_code
            job.output_events = self._output_events(job, stdout=result.stdout, stderr=result.stderr)
            next_status = JobStatus.SUCCESS if result.exit_code == 0 else JobStatus.FAILED
            if await self._cancelled(job, transition=False):
                next_status = JobStatus.CANCELLED
            await self.transition(job, next_status, started_at=started)
        except Exception as exc:
            if await self._cancelled(job, transition=False):
                job.stderr = str(exc) or "Job cancelled during execution"
                await self.transition(job, JobStatus.CANCELLED, started_at=started)
            else:
                job.stdout = ""
                job.stderr = str(exc)
                job.exit_code = None
                job.output_events = self._output_events(job, stderr=str(exc))
                await self.transition(job, JobStatus.FAILED, started_at=started)

        await self._audit(job, server)
        self.cancellation_registry.clear(job.id)
        return job

    async def transition(self, job: Job, next_status: JobStatus, *, started_at: datetime | None = None) -> None:
        current = job.status
        if current == next_status:
            return
        if next_status not in VALID_JOB_TRANSITIONS[current]:
            raise InvalidJobStateTransitionError(f"Cannot transition job from {current.value} to {next_status.value}")
        now = datetime.now(UTC)
        job.status = next_status
        if next_status == JobStatus.QUEUED:
            job.queued_at = job.queued_at or now
        elif next_status == JobStatus.DISPATCHED:
            job.dispatched_at = job.dispatched_at or now
        elif next_status == JobStatus.RUNNING:
            job.started_at = job.started_at or now
        elif next_status in TERMINAL_JOB_STATES:
            job.completed_at = job.completed_at or now
            start = started_at or job.started_at or job.queued_at
            job.runtime_duration_seconds = duration_seconds(
                start,
                job.completed_at,
                default_to_now=False,
            )
        job.runtime_metadata = {
            **(job.runtime_metadata or {}),
            "last_transition_at": now.isoformat(),
            "terminal": next_status in TERMINAL_JOB_STATES,
        }
        await self.job_repository.session.commit()
        await self.job_repository.session.refresh(job)

    async def request_cancel(self, job: Job, *, reason: str = "cancel_requested") -> Job:
        intent = self.cancellation_registry.request(job.id, reason=reason)
        job.cancellation_requested_at = intent.requested_at
        job.runtime_metadata = {
            **(job.runtime_metadata or {}),
            "cancellation_intent": reason,
            "cancellation_requested_at": intent.requested_at.isoformat(),
        }
        if job.status in {JobStatus.PENDING, JobStatus.QUEUED, JobStatus.DISPATCHED, JobStatus.RUNNING}:
            await self.transition(job, JobStatus.CANCELLED)
        else:
            await self.job_repository.session.commit()
            await self.job_repository.session.refresh(job)
        return job

    async def _cancelled(self, job: Job, *, transition: bool = True) -> bool:
        if self.cancellation_registry.get(job.id) is None and job.cancellation_requested_at is None:
            return False
        if transition and job.status not in TERMINAL_JOB_STATES:
            await self.transition(job, JobStatus.CANCELLED)
        return True

    async def _credentials(self, server, payload: JobExecuteRequest):
        ssh_user = server.ssh_username
        ssh_password = server.ssh_password if server.ssh_auth_method == ServerSshAuthMethod.PASSWORD else None
        ssh_private_key_path = server.ssh_private_key_path if server.ssh_auth_method == ServerSshAuthMethod.KEY else None
        ssh_private_key: str | None = None
        ssh_passphrase: str | None = None
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
                ssh_private_key_path = None
                ssh_private_key = credential.private_key
                ssh_passphrase = credential.passphrase
        return ssh_user, ssh_password, ssh_private_key_path, ssh_private_key, ssh_passphrase

    async def _audit(self, job: Job, server) -> None:
        if self.audit_service is None:
            return
        await self.audit_service.record(
            event_type=self._audit_event_type(job.operation_type),
            target_type="server",
            target_id=server.id,
            result="success" if job.status == JobStatus.SUCCESS else "failed",
            metadata={
                "job_id": str(job.id),
                "operation_type": job.operation_type,
                "exit_code": job.exit_code,
                "target_hostname": server.hostname,
                "correlation_id": job.correlation_id,
                "runtime_duration_seconds": job.runtime_duration_seconds,
            },
            error=job.stderr if job.status != JobStatus.SUCCESS else None,
        )

    @staticmethod
    def _output_events(job: Job, *, stdout: str = "", stderr: str = "") -> list[dict[str, object]]:
        now = datetime.now(UTC).isoformat()
        events = list(job.output_events or [])
        if stdout:
            events.append({"stream": "stdout", "content": stdout, "created_at": now, "sequence": len(events) + 1})
        if stderr:
            events.append({"stream": "stderr", "content": stderr, "created_at": now, "sequence": len(events) + 1})
        return events

    @staticmethod
    def _origin(operation_type: str) -> str:
        return operation_type.split(":", 1)[0] or "manual"

    @staticmethod
    def _audit_event_type(operation_type: str) -> str:
        prefix = operation_type.split(":", 1)[0]
        return {
            "action": "job.action_executed",
            "package": "package.executed",
            "profile": "profile.executed",
            "deployment": "deployment.action_executed",
            "provisioning": "provisioning.action_executed",
            "identity": "identity.action_executed",
        }.get(prefix, "job.executed")


execution_cancellations = ExecutionCancellationRegistry()

```

## backend/app/modules/jobs/service.py

```python
import asyncio
from uuid import UUID
from uuid import uuid4

import structlog
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.adapters.ssh import SshAdapter
from backend.app.modules.audit.repository import AuditEventRepository
from backend.app.modules.audit.service import AuditService
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.models import InventoryLifecycleState
from backend.app.modules.jobs.actions import get_action, list_actions
from backend.app.modules.jobs.models import CustomOperationalAction, Job, JobStatus
from backend.app.modules.jobs.repository import CustomOperationalActionRepository, JobRepository
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
        if get_action(payload.id) or await self.action_repository.get_by_slug(payload.id):
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
        await self.action_repository.delete(action)
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
            )
        )

    async def execute(self, payload: JobExecuteRequest) -> JobRead:
        server = await self.server_repository.get_by_id(payload.target_server_id)
        if server is None:
            raise JobTargetNotFoundError("Target server not found")
        if not server.managed or server.lifecycle_state in {
            InventoryLifecycleState.ARCHIVED,
            InventoryLifecycleState.DECOMMISSIONED,
            InventoryLifecycleState.DELETED,
        }:
            raise JobTargetNotManagedError("Target server is not managed")

        job = Job(
            target_server_id=server.id,
            operation_type=payload.operation_type,
            command=payload.redacted_command or payload.command,
            status=JobStatus.PENDING,
            execution_origin=payload.operation_type.split(":", 1)[0] or "manual",
            correlation_id=str(uuid4()),
            runtime_metadata={
                "execution_origin": payload.operation_type.split(":", 1)[0] or "manual",
                "operation_type": payload.operation_type,
                "target_hostname": server.hostname,
            },
        )
        job = await self.job_repository.create(job)
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

        logger.info(
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
                    success=job.status == JobStatus.SUCCESS,
                    job=job,
                    error=job.stderr if job.status in {JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.STALE} else None,
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
        success_count = sum(1 for result in results if result.success)
        return BulkExecutionRead(
            operation_type=payload.operation_type,
            success_count=success_count,
            failure_count=len(results) - success_count,
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
        return data.model_copy(update={"target_hostname": server.hostname if server else None})

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

```

## backend/app/modules/jobs/models.py

```python
from enum import StrEnum
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class JobStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    COMPLETED = "completed"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STALE = "stale"


class Job(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "jobs"

    target_server_id: Mapped[UUID] = mapped_column(ForeignKey("servers.id"), index=True)
    operation_type: Mapped[str] = mapped_column(String(100), index=True)
    command: Mapped[str] = mapped_column(Text)
    status: Mapped[JobStatus] = mapped_column(
        Enum(
            JobStatus,
            name="job_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=JobStatus.PENDING,
        nullable=False,
        index=True,
    )
    stdout: Mapped[str | None] = mapped_column(Text)
    stderr: Mapped[str | None] = mapped_column(Text)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    runtime_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    execution_origin: Mapped[str] = mapped_column(String(100), default="manual", nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(100), index=True)
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    runtime_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    output_events: Mapped[list] = mapped_column(JSON, default=list, nullable=False)


class CustomOperationalAction(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "custom_operational_actions"

    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str] = mapped_column(String(100), index=True, default="Custom")
    description: Mapped[str] = mapped_column(Text, default="")
    command: Mapped[str] = mapped_column(Text)
    destructive: Mapped[bool] = mapped_column(default=False, nullable=False)

```

## backend/app/modules/jobs/schemas.py

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.modules.jobs.models import JobStatus


class JobExecuteRequest(BaseModel):
    target_server_id: UUID
    command: str = Field(min_length=1, max_length=20000)
    redacted_command: str | None = Field(default=None, min_length=1, max_length=20000)
    operation_type: str = Field(default="command", min_length=1, max_length=100)
    credential_ref: str | None = Field(default=None, max_length=255)

    @field_validator("command", "redacted_command", "operation_type")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped


class JobBulkExecuteRequest(BaseModel):
    target_server_ids: list[UUID] = Field(min_length=1)
    command: str = Field(min_length=1, max_length=20000)
    redacted_command: str | None = Field(default=None, min_length=1, max_length=20000)
    operation_type: str = Field(default="command", min_length=1, max_length=100)
    credential_ref: str | None = Field(default=None, max_length=255)
    max_parallel: int = Field(default=4, ge=1, le=20)

    @field_validator("target_server_ids")
    @classmethod
    def dedupe_target_server_ids(cls, value: list[UUID]) -> list[UUID]:
        return list(dict.fromkeys(value))

    @field_validator("command", "redacted_command", "operation_type")
    @classmethod
    def strip_bulk_required_strings(cls, value: str) -> str:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped


class OperationalActionRead(BaseModel):
    id: str
    name: str
    category: str
    description: str
    command: str
    destructive: bool = False
    is_builtin: bool = True


class OperationalActionCreate(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(default="Custom", min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    command: str = Field(min_length=1, max_length=20000)
    destructive: bool = False

    @field_validator("id", "name", "category", "command")
    @classmethod
    def strip_action_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @field_validator("description")
    @classmethod
    def strip_action_description(cls, value: str) -> str:
        return value.strip()


class OperationalActionUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(default="Custom", min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    command: str = Field(min_length=1, max_length=20000)
    destructive: bool = False

    @field_validator("name", "category", "command")
    @classmethod
    def strip_update_action_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @field_validator("description")
    @classmethod
    def strip_update_action_description(cls, value: str) -> str:
        return value.strip()


class JobActionExecuteRequest(BaseModel):
    target_server_id: UUID
    action_id: str = Field(min_length=1, max_length=100)
    credential_ref: str | None = Field(default=None, max_length=255)

    @field_validator("action_id")
    @classmethod
    def strip_action_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped


class JobRead(BaseModel):
    id: UUID
    target_server_id: UUID
    target_hostname: str | None = None
    operation_type: str
    command: str
    status: JobStatus
    stdout: str | None = None
    stderr: str | None = None
    exit_code: int | None = None
    queued_at: datetime | None = None
    dispatched_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    runtime_duration_seconds: int | None = None
    execution_origin: str = "manual"
    correlation_id: str | None = None
    cancellation_requested_at: datetime | None = None
    runtime_metadata: dict[str, object] = Field(default_factory=dict)
    output_events: list[dict[str, object]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BulkExecutionHostResult(BaseModel):
    target_server_id: UUID
    target_hostname: str | None = None
    success: bool
    job: JobRead | None = None
    error: str | None = None


class BulkExecutionRead(BaseModel):
    operation_type: str
    success_count: int
    failure_count: int
    results: list[BulkExecutionHostResult]

```

## frontend/src/features/inventory/pages/HostDetailPage.tsx

```tsx
import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Activity, Box, ExternalLink, HardDrive, Loader2, Play, Power, RefreshCw, RotateCw, ServerIcon, ShieldCheck, TerminalSquare } from 'lucide-react';

import { PageHeader } from '../../../components/layout/PageHeader';
import { getApiErrorMessage } from '../../../lib/api/client';
import { listAutomations } from '../../automations/api/automationsApi';
import type { Automation } from '../../automations/types/automation';
import { useAuth } from '../../auth/hooks/useAuth';
import { listDeployments } from '../../deployments/api/deploymentsApi';
import type { Deployment } from '../../deployments/types/deployment';
import { listLinuxGroups, listLinuxUsers, listSSHKeys } from '../../identity/api/identityApi';
import type { LinuxGroup, LinuxUser, SSHKey } from '../../identity/types/identity';
import { listJobs } from '../../jobs/api/jobsApi';
import type { Job } from '../../jobs/types/job';
import { getServerMetrics } from '../../monitoring/api/monitoringApi';
import type { ServerMetrics } from '../../monitoring/types/monitoring';
import { runVmAction } from '../../proxmox/api/proxmoxApi';
import type { ProxmoxVmAction } from '../../proxmox/types/proxmox';
import { FileBrowserPanel } from '../../remote-access/components/FileBrowserPanel';
import { ShellPanel } from '../../remote-access/components/ShellPanel';
import { RuntimeStateBadge } from '../../runtime-state/components/RuntimeStateBadge';
import { canRunLifecycleAction } from '../../runtime-state/utils/eligibility';
import { listWorkflows } from '../../workflows/api/workflowsApi';
import type { WorkflowRun } from '../../workflows/types/workflow';
import {
  getServer,
  getServerDocker,
  getServerNetwork,
  getServerSystem,
} from '../api/serversApi';
import type { HostDocker, HostNetwork, HostSystem, Server } from '../types/server';
import { EnvironmentBadge, HealthBadge, LifecycleBadge, SyncBadge } from '../components/ServerBadges';

type LoadState = {
  server: Server | null;
  system: HostSystem | null;
  network: HostNetwork | null;
  docker: HostDocker | null;
  metrics: ServerMetrics | null;
  deployments: Deployment[];
  jobs: Job[];
  workflows: WorkflowRun[];
  automations: Automation[];
  users: LinuxUser[];
  groups: LinuxGroup[];
  sshKeys: SSHKey[];
};

type HostTab = 'overview' | 'operations' | 'runtime' | 'access' | 'automation';

const initialState: LoadState = {
  server: null,
  system: null,
  network: null,
  docker: null,
  metrics: null,
  deployments: [],
  jobs: [],
  workflows: [],
  automations: [],
  users: [],
  groups: [],
  sshKeys: [],
};

export function HostDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [state, setState] = useState<LoadState>(initialState);
  const [errors, setErrors] = useState<string[]>([]);
  const [notice, setNotice] = useState<{ tone: 'success' | 'error'; message: string } | null>(null);
  const [activeVmAction, setActiveVmAction] = useState<ProxmoxVmAction | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<HostTab>('overview');
  const allowManagement = user?.role === 'admin' || user?.role === 'operator';

  const refresh = useCallback(async () => {
    if (!id) {
      return;
    }
    setIsLoading(true);
    setErrors([]);

    const serverResult = await settle(() => getServer(id));
    if (!serverResult.ok) {
      setErrors([serverResult.error]);
      setIsLoading(false);
      return;
    }

    const [system, network, docker, metrics, deployments, jobs, workflows, automations, users, groups, sshKeys] =
      await Promise.all([
        settle(() => getServerSystem(id)),
        settle(() => getServerNetwork(id)),
        settle(() => getServerDocker(id)),
        settle(() => getServerMetrics(id)),
        settle(() => listDeployments({ serverId: id })),
        settle(() => listJobs({ targetServerId: id })),
        settle(() => listWorkflows({ targetServerId: id })),
        settle(() => listAutomations({ targetServerId: id })),
        settle(() => listLinuxUsers()),
        settle(() => listLinuxGroups()),
        settle(() => listSSHKeys()),
      ]);

    setState({
      server: serverResult.value,
      system: system.ok ? system.value : null,
      network: network.ok ? network.value : null,
      docker: docker.ok ? docker.value : null,
      metrics: metrics.ok ? metrics.value : null,
      deployments: deployments.ok ? deployments.value : [],
      jobs: jobs.ok ? jobs.value.slice(0, 8) : [],
      workflows: workflows.ok ? workflows.value.slice(0, 8) : [],
      automations: automations.ok ? automations.value.slice(0, 8) : [],
      users: users.ok ? users.value : [],
      groups: groups.ok ? groups.value : [],
      sshKeys: sshKeys.ok ? sshKeys.value : [],
    });
    setErrors(
      [system, network, docker, metrics, deployments, jobs, workflows, automations, users, groups, sshKeys]
        .filter((result) => !result.ok)
        .map((result) => (result.ok ? '' : result.error)),
    );
    setIsLoading(false);
  }, [id]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const exporterState = useMemo(() => detectExporters(state), [state]);

  async function handleVmLifecycle(action: ProxmoxVmAction) {
    const server = state.server;
    const vmId = getProviderVmId(server);
    if (!server || vmId === null) {
      setNotice({ tone: 'error', message: 'This inventory host is not linked to a Proxmox VMID.' });
      return;
    }

    if (action !== 'start') {
      const confirmed = window.confirm(`${actionLabel(action)} ${server.node_type === 'lxc' ? 'LXC' : 'VM'} ${server.hostname} (${vmId})?`);
      if (!confirmed) {
        return;
      }
    }

    setActiveVmAction(action);
    setNotice(null);
    try {
      const response = await runVmAction(vmId, action);
      setNotice({ tone: 'success', message: response.message });
      await refresh();
    } catch (caughtError) {
      setNotice({ tone: 'error', message: getApiErrorMessage(caughtError) });
    } finally {
      setActiveVmAction(null);
    }
  }

  if (isLoading && !state.server) {
    return <div className="h-80 animate-pulse rounded-lg bg-zinc-100" />;
  }

  if (!state.server) {
    return <ErrorPanel title="Host could not be loaded" errors={errors} onRetry={refresh} />;
  }

  const server = state.server;

  return (
    <div className="space-y-6">
      <PageHeader
        title={server.hostname}
        description="Unified operations for this managed node across inventory, provider, monitoring, remote access, jobs, deployments, and identity."
      />

      {notice ? <HostNotice message={notice.message} tone={notice.tone} onDismiss={() => setNotice(null)} /> : null}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          <EnvironmentBadge environment={server.environment} />
          <LifecycleBadge state={server.lifecycle_state} />
          <SyncBadge status={server.sync_status} />
          <HealthBadge status={server.last_health_status} />
          <RuntimeStateBadge runtimeState={server.runtime_state} />
          <ReadinessBadge readiness={nodeReadiness(server, state)} />
          <NodeTypePill nodeType={server.node_type} />
        </div>
        <button
          className="inline-flex items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
          type="button"
          onClick={() => void refresh()}
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Refresh
        </button>
        <Link
          className="inline-flex items-center gap-2 rounded-md bg-zinc-900 px-3 py-2 text-sm font-semibold text-white hover:bg-zinc-800"
          to={`/inventory/${server.id}/tools`}
        >
          <TerminalSquare className="h-4 w-4" aria-hidden="true" />
          Host Tools
        </Link>
      </div>

      {errors.length ? <ErrorPanel title="Some live checks failed" errors={errors} onRetry={refresh} compact /> : null}

      <nav className="flex gap-2 overflow-x-auto rounded-lg border border-zinc-200 bg-white p-2 shadow-sm">
        {hostTabs.map((tab) => (
          <button
            key={tab.id}
            className={`whitespace-nowrap rounded-md px-3 py-2 text-sm font-semibold ${
              activeTab === tab.id ? 'bg-zinc-950 text-white' : 'text-zinc-600 hover:bg-zinc-100 hover:text-zinc-950'
            }`}
            type="button"
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {activeTab !== 'overview' ? (
        <HostTabPanel
          activeVmAction={activeVmAction}
          allowManagement={allowManagement}
          canUseRemoteAccess={allowManagement && Boolean(server.runtime_state?.eligibility.can_open_shell ?? true)}
          server={server}
          state={state}
          tab={activeTab}
          onVmLifecycle={(action) => void handleVmLifecycle(action)}
        />
      ) : null}

      {activeTab === 'overview' ? (
        <>
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={ServerIcon} label="LAN IP" value={state.network?.lan_ip ?? server.ip_address} />
        <MetricCard icon={Activity} label="Uptime" value={formatDuration(state.system?.uptime_seconds ?? state.metrics?.uptime_seconds)} />
        <MetricCard icon={HardDrive} label="Memory" value={formatPercent(bytesPercent(state.system?.memory_used_bytes, state.system?.memory_total_bytes) ?? state.metrics?.memory_usage_percent)} />
        <MetricCard icon={Box} label="Readiness" value={formatReadiness(nodeReadiness(server, state))} />
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-6">
          <OperationalInsightsPanel server={server} state={state} />

          <Panel title="System Overview">
            <dl className="grid gap-3 sm:grid-cols-2">
              <Info label="Node type" value={formatNodeType(server.node_type)} />
              <Info label="OS" value={state.system?.operating_system ?? server.operating_system} />
              <Info label="Kernel" value={state.system?.kernel ?? 'Unknown'} />
              <Info label="CPU" value={state.system?.cpu_model ?? 'Unknown'} />
              <Info label="Cores" value={state.system?.cpu_cores ? String(state.system.cpu_cores) : 'Unknown'} />
              <Info label="Load" value={state.system?.load_average.join(' / ') || 'Unknown'} />
              <Info label="Provider" value={`${server.provider}${server.provider_node ? ` / ${server.provider_node}` : ''}`} />
              <Info label="Lifecycle" value={server.lifecycle_state} />
              <Info label="Operational state" value={nodeReadiness(server, state)} />
              <Info label="SSH readiness" value={server.runtime_state?.ssh_state ?? sshReadiness(server, state)} />
              <Info label="Monitoring state" value={server.runtime_state?.monitoring_state ?? monitoringReadiness(state)} />
              <Info label="Provider state" value={server.runtime_state?.provider_state ?? 'unknown'} />
            </dl>
          </Panel>

          <ReconciliationPanel server={server} />

          <Panel title="Provider Metadata">
            <div className="grid gap-3 md:grid-cols-2">
              <Info label="Provider" value={server.provider} />
              <Info label="Provider type" value={server.provider_type ?? 'Unknown'} />
              <Info label="Provider node" value={server.provider_node ?? 'Unknown'} />
              <Info label="External ID" value={server.external_id ?? server.vmid ?? 'Unknown'} />
            </div>
            <MetadataBlock metadata={server.provider_metadata} />
          </Panel>

          <Panel title="Filesystems">
            <div className="grid gap-3 md:grid-cols-2">
              {(state.system?.filesystems ?? []).map((fs) => (
                <div key={`${fs.filesystem}-${fs.mountpoint}`} className="rounded-md border border-zinc-200 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-mono text-sm font-semibold text-zinc-950">{fs.mountpoint}</span>
                    <span className="text-xs text-zinc-500">{fs.type}</span>
                  </div>
                  <div className="mt-3 h-2 rounded-full bg-zinc-100">
                    <div className="h-2 rounded-full bg-zinc-900" style={{ width: `${bytesPercent(fs.used_bytes, fs.size_bytes) ?? 0}%` }} />
                  </div>
                  <p className="mt-2 text-xs text-zinc-500">{formatBytes(fs.used_bytes)} / {formatBytes(fs.size_bytes)}</p>
                </div>
              ))}
              {state.system?.filesystems.length === 0 ? <EmptyText text="No filesystem data collected." /> : null}
            </div>
          </Panel>

          <Panel title="Network">
            <div className="grid gap-4 lg:grid-cols-2">
              <div>
                <h4 className="text-sm font-semibold text-zinc-950">Interfaces</h4>
                <div className="mt-3 space-y-2">
                  {(state.network?.interfaces ?? []).map((item) => (
                    <div key={item.name} className="rounded-md border border-zinc-200 p-3">
                      <div className="font-mono text-sm font-semibold">{item.name}</div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {item.addresses.map((address) => (
                          <span key={address} className="rounded bg-zinc-100 px-2 py-1 font-mono text-xs text-zinc-700">{address}</span>
                        ))}
                      </div>
                    </div>
                  ))}
                  {state.network?.interfaces.length === 0 ? <EmptyText text="No interfaces discovered." /> : null}
                </div>
              </div>
              <div>
                <h4 className="text-sm font-semibold text-zinc-950">Listening Services</h4>
                <div className="mt-3 space-y-2">
                  {(state.network?.listening_ports ?? []).map((port) => (
                    <div key={`${port.protocol}-${port.address}-${port.port}`} className="flex items-center justify-between gap-3 rounded-md border border-zinc-200 p-3">
                      <div>
                        <div className="font-mono text-sm font-semibold">{port.port}/{port.protocol}</div>
                        <div className="text-xs text-zinc-500">{port.process ?? port.service ?? 'unknown process'}</div>
                      </div>
                      {serviceUrl(server.ip_address, port) ? (
                        <a className="inline-flex items-center gap-1 text-xs font-semibold text-zinc-700 hover:text-zinc-950" href={serviceUrl(server.ip_address, port) ?? undefined} target="_blank" rel="noreferrer">
                          Open <ExternalLink className="h-3 w-3" aria-hidden="true" />
                        </a>
                      ) : null}
                    </div>
                  ))}
                  {state.network?.listening_ports.length === 0 ? <EmptyText text="No listening ports discovered." /> : null}
                </div>
              </div>
            </div>
          </Panel>

          <Panel title="Docker Runtime">
            <div className="mb-4 flex flex-wrap gap-2">
              <Badge tone={state.docker?.installed ? 'success' : 'muted'}>{state.docker?.installed ? `Docker ${state.docker.version}` : 'Docker not detected'}</Badge>
              <Badge tone="muted">Restart quick actions planned</Badge>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-zinc-200 text-sm">
                <thead className="bg-zinc-50">
                  <tr>{['Container', 'Image', 'Status', 'Ports', 'Compose'].map((heading) => <th key={heading} className="px-3 py-2 text-left text-xs font-semibold uppercase text-zinc-500">{heading}</th>)}</tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {(state.docker?.containers ?? []).map((container) => (
                    <tr key={container.container_id}>
                      <td className="px-3 py-2 font-semibold">{container.name}</td>
                      <td className="px-3 py-2 font-mono text-xs">{container.image}</td>
                      <td className="px-3 py-2"><Badge tone={container.status.toLowerCase().includes('up') ? 'success' : 'muted'}>{container.status}</Badge></td>
                      <td className="px-3 py-2 font-mono text-xs">{container.ports || '-'}</td>
                      <td className="px-3 py-2">{container.compose_project ?? '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {state.docker?.containers.length === 0 ? <EmptyText text="No running containers discovered." /> : null}
            </div>
          </Panel>
        </div>

        <aside className="space-y-6">
          <Panel title="Monitoring">
            <div className="space-y-2">
              <Badge tone={state.metrics?.monitoring_state === 'monitored' ? 'success' : 'warning'}>
                {formatReadiness(state.metrics?.monitoring_state ?? monitoringReadiness(state))}
              </Badge>
              <Badge tone={state.metrics?.metrics_available ? 'success' : 'warning'}>metrics {state.metrics?.metrics_available ? 'available' : 'missing'}</Badge>
              <Badge tone={state.metrics?.logs_available ? 'success' : 'warning'}>logs {state.metrics?.logs_available ? 'available' : 'missing'}</Badge>
              <Badge tone={exporterState.node ? 'success' : 'muted'}>node_exporter {exporterState.node ? 'detected' : 'not detected'}</Badge>
              <Badge tone={exporterState.promtail ? 'success' : 'muted'}>promtail {exporterState.promtail ? 'detected' : 'not detected'}</Badge>
              <Badge tone={exporterState.cadvisor ? 'success' : 'muted'}>cadvisor {exporterState.cadvisor ? 'detected' : 'not detected'}</Badge>
              {state.metrics?.stale_metrics ? <Badge tone="warning">stale metrics</Badge> : null}
            </div>
            {state.metrics?.open_grafana_url ? (
              <a className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-zinc-800 hover:text-zinc-950" href={state.metrics.open_grafana_url} target="_blank" rel="noreferrer">
                Open Grafana <ExternalLink className="h-4 w-4" aria-hidden="true" />
              </a>
            ) : null}
          </Panel>

          <Panel title="Related Resources">
            <LinkList items={[
              { label: `${state.deployments.length} deployments`, to: '/deployments' },
              { label: `${state.jobs.length} recent jobs`, to: '/jobs' },
              { label: `${state.workflows.length} recent workflows`, to: '/workflows' },
              { label: `${state.automations.length} automations targeting node`, to: '/automations' },
              { label: `${state.users.length} users / ${state.groups.length} groups`, to: '/identity' },
              { label: `${state.sshKeys.length} SSH keys`, to: '/identity' },
            ]} />
          </Panel>

          <Panel title="Quick Actions">
            <LinkList items={[
              { label: 'Open dedicated host tools', to: `/inventory/${server.id}/tools` },
              { label: 'Run command', to: '/jobs' },
              { label: 'Apply profile', to: '/profiles' },
              { label: 'Deploy compose app', to: '/deployments' },
              { label: 'View monitoring', to: '/monitoring' },
            ]} />
          </Panel>

          <Panel title="Identity Scope">
            <div className="flex items-center gap-3 text-sm text-zinc-600">
              <ShieldCheck className="h-5 w-5 text-zinc-500" aria-hidden="true" />
              Linux identity orchestration is available through Jobs-backed replication.
            </div>
          </Panel>
        </aside>
      </section>
        </>
      ) : null}
    </div>
  );
}

const hostTabs: Array<{ id: HostTab; label: string }> = [
  { id: 'overview', label: 'Overview' },
  { id: 'operations', label: 'Operations' },
  { id: 'runtime', label: 'Runtime' },
  { id: 'access', label: 'Access' },
  { id: 'automation', label: 'Automation' },
];

function HostTabPanel({
  activeVmAction,
  allowManagement,
  canUseRemoteAccess,
  tab,
  server,
  state,
  onVmLifecycle,
}: {
  activeVmAction: ProxmoxVmAction | null;
  allowManagement: boolean;
  canUseRemoteAccess: boolean;
  tab: HostTab;
  server: Server;
  state: LoadState;
  onVmLifecycle: (action: ProxmoxVmAction) => void;
}) {
  if (tab === 'operations') {
    return (
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Panel title="Lifecycle actions">
          <div className="space-y-4">
          <div className="grid gap-3 md:grid-cols-3">
            <Info label="Provider" value={server.provider} />
            <Info label="Node" value={server.provider_node ?? 'Unknown'} />
            <Info label="VMID" value={String(getProviderVmId(server) ?? 'Not linked')} />
          </div>
          <VmLifecycleActions
            activeAction={activeVmAction}
            allowManagement={allowManagement}
            server={server}
            onAction={onVmLifecycle}
          />
          {!allowManagement ? <p className="text-sm text-zinc-500">Operator or admin role required for VM lifecycle actions.</p> : null}
          </div>
        </Panel>
        <EligibilityPanel server={server} />
      </div>
    );
  }

  if (tab === 'access') {
    return (
      <div className="grid gap-6 xl:grid-cols-2">
        <div className="min-h-[520px]">
          <ShellPanel server={server} canUseShell={canUseRemoteAccess} compact />
        </div>
        <FileBrowserPanel server={server} canUseFiles={canUseRemoteAccess} />
      </div>
    );
  }

  if (tab === 'automation') {
    return (
      <div className="grid gap-6 xl:grid-cols-2">
        <Panel title="Deployments">
          <LinkList items={[
            ...state.deployments.map((deployment) => ({ label: `${deployment.name} - ${deployment.status}`, to: '/deployments' })),
            { label: 'Create deployment for this host', to: '/deployments' },
          ]} />
        </Panel>
        <Panel title="Jobs">
          <LinkList items={[
            ...state.jobs.map((job) => ({ label: `${job.operation_type} - ${job.status}`, to: '/jobs' })),
            { label: 'Run command for this host', to: '/jobs' },
          ]} />
        </Panel>
        <Panel title="Workflows and automations">
          <LinkList items={[
            ...state.workflows.map((workflow) => ({
              label: `${formatReadiness(workflow.workflow_type)} - ${workflow.status} - ${workflowProgress(workflow)}`,
              to: '/workflows',
            })),
            ...state.automations.map((automation) => ({
              label: `${automation.name} automation - ${automation.runtime_state}`,
              to: '/automations',
            })),
            { label: 'Open workflow history', to: '/workflows' },
          ]} />
        </Panel>
        <Panel title="Profiles and packages">
          <LinkList items={[
            { label: 'Run package against this host', to: '/packages' },
            { label: 'Apply profile to this host', to: '/profiles' },
          ]} />
        </Panel>
      </div>
    );
  }

  if (tab === 'runtime') {
    return (
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Panel title="Monitoring and freshness">
          <div className="grid gap-3 md:grid-cols-3">
            <Info label="Uptime" value={formatDuration(state.metrics?.uptime_seconds)} />
            <Info label="CPU" value={formatPercent(state.metrics?.cpu_usage_percent)} />
            <Info label="Memory" value={formatPercent(state.metrics?.memory_usage_percent)} />
            <Info label="Observability" value={formatReadiness(server.runtime_state?.observability_state ?? monitoringReadiness(state))} />
            <Info label="Runtime freshness" value={formatDateTime(server.runtime_state?.freshness.runtime_refreshed_at)} />
            <Info label="Confidence" value={formatReadiness(server.runtime_state?.freshness.confidence ?? 'unknown')} />
          </div>
        </Panel>
        <OperationalNoticesPanel server={server} />
      </div>
    );
  }

  return null;
}

function OperationalInsightsPanel({ server, state }: { server: Server; state: LoadState }) {
  const runtime = server.runtime_state;
  return (
    <Panel title="Operational insights">
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="grid gap-3 sm:grid-cols-2">
          <Info label="Administrative state" value={formatReadiness(runtime?.administrative_state ?? server.lifecycle_state)} />
          <Info label="Infrastructure state" value={formatReadiness(runtime?.infrastructure_state ?? runtime?.provider_state ?? 'unknown')} />
          <Info label="Orchestration state" value={formatReadiness(runtime?.orchestration_state ?? nodeReadiness(server, state))} />
          <Info label="Observability state" value={formatReadiness(runtime?.observability_state ?? monitoringReadiness(state))} />
          <Info label="SSH readiness" value={formatReadiness(runtime?.ssh_state ?? sshReadiness(server, state))} />
          <Info label="Runtime readiness" value={formatReadiness(runtime?.readiness_state ?? nodeReadiness(server, state))} />
        </div>
        <OperationalNoticesPanel server={server} compact />
      </div>
    </Panel>
  );
}

function ReconciliationPanel({ server }: { server: Server }) {
  const reconciliation = server.runtime_state?.reconciliation;
  return (
    <Panel title="Reconciliation">
      <div className="grid gap-3 md:grid-cols-2">
        <Info label="Provider link" value={formatReadiness(reconciliation?.provider_link_status ?? providerLinkStatus(server))} />
        <Info label="Confidence" value={formatReadiness(reconciliation?.confidence ?? 'unknown')} />
        <Info label="Provider sync" value={formatReadiness(reconciliation?.provider_sync_freshness ?? server.sync_state)} />
        <Info label="Last reconciled" value={formatDateTime(reconciliation?.last_reconciled_at ?? server.last_sync_at ?? server.last_seen_at)} />
      </div>
      <NoticeList
        emptyText="No reconciliation drift detected."
        items={[...(reconciliation?.drift_indicators ?? []), ...(reconciliation?.mismatch_explanations ?? [])]}
      />
    </Panel>
  );
}

function EligibilityPanel({ server }: { server: Server }) {
  const eligibility = server.runtime_state?.eligibility;
  const actions = [
    ['can_open_shell', 'Shell'],
    ['can_run_jobs', 'Jobs'],
    ['can_deploy', 'Deployments'],
    ['can_apply_profiles', 'Profiles'],
    ['can_manage_identity', 'Identity'],
    ['can_start', 'Start'],
    ['can_stop', 'Stop'],
    ['can_reboot', 'Reboot'],
    ['can_sync_provider', 'Provider sync'],
  ] as const;
  return (
    <Panel title="Runtime eligibility">
      <div className="space-y-3">
        {actions.map(([key, label]) => {
          const allowed = Boolean(eligibility?.[key] ?? false);
          const blockers = eligibility?.blockers?.[key] ?? [];
          return (
            <div key={key} className="rounded-md border border-zinc-200 p-3">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-semibold text-zinc-950">{label}</span>
                <Badge tone={allowed ? 'success' : 'warning'}>{allowed ? 'Allowed' : 'Blocked'}</Badge>
              </div>
              {!allowed ? <p className="mt-2 text-xs text-zinc-500">{blockers.map(formatReadiness).join(', ') || 'Policy not satisfied'}</p> : null}
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function OperationalNoticesPanel({ server, compact = false }: { server: Server; compact?: boolean }) {
  const runtime = server.runtime_state;
  const items = [
    ...(runtime?.degraded_reasons ?? []),
    ...(runtime?.stale_reasons ?? []),
    ...(runtime?.warnings ?? []),
  ];
  return (
    <div className={compact ? '' : 'space-y-4'}>
      <NoticeList emptyText="No runtime warnings reported." items={items} />
      {!compact ? (
        <div className="grid gap-3">
          <Info label="Provider refresh" value={formatDateTime(runtime?.freshness.provider_refreshed_at)} />
          <Info label="Monitoring refresh" value={formatDateTime(runtime?.freshness.monitoring_refreshed_at)} />
          <Info label="Inventory refresh" value={formatDateTime(runtime?.freshness.inventory_refreshed_at)} />
        </div>
      ) : null}
    </div>
  );
}

function NoticeList({ emptyText, items }: { emptyText: string; items: string[] }) {
  const uniqueItems = Array.from(new Set(items.filter(Boolean)));
  if (!uniqueItems.length) {
    return <EmptyText text={emptyText} />;
  }
  return (
    <div className="mt-4 space-y-2">
      {uniqueItems.map((item) => (
        <div key={item} className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {formatReadiness(item)}
        </div>
      ))}
    </div>
  );
}

function HostNotice({
  message,
  tone,
  onDismiss,
}: {
  message: string;
  tone: 'success' | 'error';
  onDismiss: () => void;
}) {
  const className =
    tone === 'success'
      ? 'border-emerald-400/30 bg-emerald-950/40 text-emerald-100'
      : 'border-rose-400/30 bg-rose-950/50 text-rose-100';
  return (
    <div className={`flex items-center justify-between gap-4 rounded-lg border px-4 py-3 ${className}`}>
      <p className="text-sm font-medium">{message}</p>
      <button className="text-sm font-semibold underline-offset-2 hover:underline" type="button" onClick={onDismiss}>
        Dismiss
      </button>
    </div>
  );
}

function ReadinessBadge({ readiness }: { readiness: string }) {
  const tone =
    readiness === 'healthy' || readiness === 'booted'
      ? 'success'
      : readiness === 'degraded' ||
          readiness === 'ssh_unreachable' ||
          readiness === 'network_missing' ||
          readiness === 'monitoring_missing' ||
          readiness === 'partially_managed'
        ? 'warning'
        : 'muted';
  return <Badge tone={tone}>{formatReadiness(readiness)}</Badge>;
}

function NodeTypePill({ nodeType }: { nodeType: Server['node_type'] }) {
  const className =
    nodeType === 'hypervisor'
      ? 'bg-violet-50 text-violet-700 ring-violet-200'
      : nodeType === 'lxc'
        ? 'bg-cyan-50 text-cyan-700 ring-cyan-200'
        : nodeType === 'vm'
          ? 'bg-indigo-50 text-indigo-700 ring-indigo-200'
          : 'bg-zinc-100 text-zinc-700 ring-zinc-200';
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${className}`}>
      {formatNodeType(nodeType)}
    </span>
  );
}

function MetadataBlock({ metadata }: { metadata: Record<string, unknown> }) {
  const entries = Object.entries(metadata).filter(([, value]) => value !== null && value !== undefined && value !== '');
  if (!entries.length) {
    return <EmptyText text="No provider metadata recorded." />;
  }
  return (
    <dl className="mt-4 grid gap-3 md:grid-cols-2">
      {entries.slice(0, 12).map(([key, value]) => (
        <Info key={key} label={key.replace(/_/g, ' ')} value={metadataValue(value)} />
      ))}
    </dl>
  );
}

function VmLifecycleActions({
  activeAction,
  allowManagement,
  server,
  onAction,
}: {
  activeAction: ProxmoxVmAction | null;
  allowManagement: boolean;
  server: Server;
  onAction: (action: ProxmoxVmAction) => void;
}) {
  const vmId = getProviderVmId(server);
  const isBusy = activeAction !== null;
  const isLinkedProxmoxVm = server.provider === 'proxmox' && vmId !== null;
  const commonDisabled = !allowManagement || !isLinkedProxmoxVm || isBusy;
  const canStart = canRunLifecycleAction(server.runtime_state, 'start') || (!server.runtime_state && isLinkedProxmoxVm);
  const canStop = canRunLifecycleAction(server.runtime_state, 'stop') || (!server.runtime_state && (server.status === 'online' || server.last_health_status === 'online'));
  const canReboot = canRunLifecycleAction(server.runtime_state, 'reboot') || (!server.runtime_state && (server.status === 'online' || server.last_health_status === 'online'));

  return (
    <div className="flex flex-wrap gap-2">
      <LifecycleButton
        action="start"
        disabled={commonDisabled || !canStart}
        icon={Play}
        isLoading={activeAction === 'start'}
        label="Start"
        tone="primary"
        onClick={() => onAction('start')}
      />
      <LifecycleButton
        action="shutdown"
        disabled={commonDisabled || !canStop}
        icon={Power}
        isLoading={activeAction === 'shutdown'}
        label="Shutdown"
        onClick={() => onAction('shutdown')}
      />
      <LifecycleButton
        action="reboot"
        disabled={commonDisabled || !canReboot}
        icon={RotateCw}
        isLoading={activeAction === 'reboot'}
        label="Reboot"
        onClick={() => onAction('reboot')}
      />
      <LifecycleButton
        action="stop"
        disabled={commonDisabled || !canStop}
        icon={Power}
        isLoading={activeAction === 'stop'}
        label="Stop"
        tone="danger"
        onClick={() => onAction('stop')}
      />
    </div>
  );
}

function LifecycleButton({
  disabled,
  icon: Icon,
  isLoading,
  label,
  onClick,
  tone = 'secondary',
}: {
  action: ProxmoxVmAction;
  disabled: boolean;
  icon: typeof Play;
  isLoading: boolean;
  label: string;
  onClick: () => void;
  tone?: 'primary' | 'secondary' | 'danger';
}) {
  const className =
    tone === 'primary'
      ? 'border-cyan-400 bg-cyan-400 text-zinc-950 hover:bg-cyan-300 disabled:border-zinc-300 disabled:bg-zinc-100 disabled:text-zinc-400'
      : tone === 'danger'
        ? 'border-rose-400/50 bg-white text-rose-700 hover:bg-rose-50 disabled:border-zinc-300 disabled:bg-zinc-100 disabled:text-zinc-400'
        : 'border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50 disabled:bg-zinc-100 disabled:text-zinc-400';
  return (
    <button
      className={`inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-semibold transition disabled:cursor-not-allowed ${className}`}
      disabled={disabled}
      type="button"
      onClick={onClick}
    >
      {isLoading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Icon className="h-4 w-4" aria-hidden="true" />}
      {label}
    </button>
  );
}

function getProviderVmId(server: Server | null): number | null {
  const raw = server?.vmid ?? server?.external_id ?? null;
  if (!raw) {
    return null;
  }
  const value = Number(raw);
  return Number.isInteger(value) && value > 0 ? value : null;
}

function actionLabel(action: ProxmoxVmAction): string {
  return action.charAt(0).toUpperCase() + action.slice(1);
}

async function settle<T>(fn: () => Promise<T>): Promise<{ ok: true; value: T } | { ok: false; error: string }> {
  try {
    return { ok: true, value: await fn() };
  } catch (error) {
    return { ok: false, error: getApiErrorMessage(error) };
  }
}

function workflowProgress(workflow: WorkflowRun): string {
  if (!workflow.steps.length) {
    return 'no steps';
  }
  const failed = workflow.failed_steps ? `, ${workflow.failed_steps} failed` : '';
  return `${workflow.completed_steps}/${workflow.steps.length} completed${failed}`;
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
      <div className="border-b border-zinc-200 px-5 py-4">
        <h3 className="text-base font-semibold text-zinc-950">{title}</h3>
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function MetricCard({ icon: Icon, label, value }: { icon: typeof ServerIcon; label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <Icon className="h-5 w-5 text-zinc-500" aria-hidden="true" />
      <div className="mt-3 text-sm text-zinc-500">{label}</div>
      <div className="mt-1 break-words text-xl font-semibold text-zinc-950">{value}</div>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase text-zinc-500">{label}</dt>
      <dd className="mt-1 break-words text-sm text-zinc-900">{value}</dd>
    </div>
  );
}

function Badge({ children, tone }: { children: ReactNode; tone: 'success' | 'warning' | 'muted' }) {
  const className = {
    success: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
    warning: 'bg-amber-50 text-amber-700 ring-amber-200',
    muted: 'bg-zinc-100 text-zinc-700 ring-zinc-200',
  }[tone];
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${className}`}>{children}</span>;
}

function EmptyText({ text }: { text: string }) {
  return <p className="py-3 text-sm text-zinc-500">{text}</p>;
}

function LinkList({ items }: { items: Array<{ label: string; to: string }> }) {
  return (
    <div className="space-y-2">
      {items.map((item) => (
        <Link key={item.label} className="flex items-center justify-between rounded-md border border-zinc-200 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50" to={item.to}>
          {item.label}
          <ExternalLink className="h-4 w-4" aria-hidden="true" />
        </Link>
      ))}
    </div>
  );
}

function ErrorPanel({ title, errors, onRetry, compact = false }: { title: string; errors: string[]; onRetry: () => void; compact?: boolean }) {
  return (
    <div className={`rounded-lg border border-amber-200 bg-amber-50 text-amber-900 ${compact ? 'p-3' : 'p-5'}`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-semibold">{title}</h3>
          <ul className="mt-2 space-y-1 text-sm">
            {errors.map((error) => <li key={error}>{error}</li>)}
          </ul>
        </div>
        <button className="rounded-md bg-amber-700 px-3 py-2 text-sm font-semibold text-white hover:bg-amber-800" type="button" onClick={onRetry}>Retry</button>
      </div>
    </div>
  );
}

function formatBytes(value: number | null | undefined): string {
  if (!value) {
    return 'Unknown';
  }
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let next = value;
  let index = 0;
  while (next >= 1024 && index < units.length - 1) {
    next /= 1024;
    index += 1;
  }
  return `${next.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function bytesPercent(used: number | null | undefined, total: number | null | undefined): number | null {
  if (!used || !total) {
    return null;
  }
  return Math.round((used / total) * 100);
}

function formatPercent(value: number | null | undefined): string {
  return value == null ? 'Unknown' : `${Math.round(value)}%`;
}

function nodeReadiness(server: Server, state: LoadState): string {
  if (server.runtime_state) {
    if (server.runtime_state.degraded_reasons.length) {
      return 'degraded';
    }
    return server.runtime_state.orchestration_state;
  }
  const metadataReadiness = String(server.provider_metadata.operational_readiness ?? '').trim();
  if (metadataReadiness) {
    if (state.metrics?.monitoring_state === 'unmonitored' && metadataReadiness === 'booted') {
      return 'monitoring_missing';
    }
    return metadataReadiness;
  }
  if (server.lifecycle_state === 'archived' || server.lifecycle_state === 'decommissioned') {
    return server.lifecycle_state;
  }
  if (!server.ip_address || server.ip_address.startsWith('0.')) {
    return 'ip_missing';
  }
  if (state.system || state.network) {
    return state.metrics?.monitoring_state === 'unmonitored' ? 'monitoring_missing' : 'healthy';
  }
  if (server.last_health_status === 'unreachable') {
    return 'ssh_unreachable';
  }
  if (server.last_health_status === 'sync_error') {
    return 'degraded';
  }
  return server.managed ? 'partially_managed' : 'discovered';
}

function sshReadiness(server: Server, state: LoadState): string {
  if (state.system || state.network) {
    return 'ready';
  }
  if (!server.ip_address || server.ip_address.startsWith('0.')) {
    return 'ip_missing';
  }
  if (server.last_health_status === 'unreachable') {
    return 'ssh_unreachable';
  }
  return server.credential_id || server.ssh_username ? 'not_verified' : 'credential_missing';
}

function monitoringReadiness(state: LoadState): string {
  return state.metrics?.monitoring_state ?? 'unknown';
}

function providerLinkStatus(server: Server): string {
  if (server.provider !== 'proxmox') {
    return 'not_provider_backed';
  }
  if (server.sync_state === 'orphaned') {
    return 'provider_guest_missing';
  }
  return server.vmid || server.external_id ? 'linked' : 'missing_provider_identity';
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return 'Unknown';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return 'Unknown';
  }
  return date.toLocaleString();
}

function formatReadiness(value: string): string {
  return value
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ') || 'Unknown';
}

function formatNodeType(value: Server['node_type']): string {
  if (value === 'lxc') return 'LXC';
  if (value === 'vm') return 'VM';
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function metadataValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.length ? value.map((item) => metadataValue(item)).join(', ') : 'None';
  }
  if (typeof value === 'object' && value !== null) {
    return JSON.stringify(value);
  }
  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No';
  }
  return String(value);
}

function formatDuration(value: number | null | undefined): string {
  if (!value) {
    return 'Unknown';
  }
  const days = Math.floor(value / 86400);
  const hours = Math.floor((value % 86400) / 3600);
  return days ? `${days}d ${hours}h` : `${hours}h`;
}

function serviceUrl(host: string, port: { port: number; service: string | null; protocol: string }): string | null {
  if (port.service === 'http' || port.port === 80) {
    return `http://${host}`;
  }
  if (port.service === 'https' || port.port === 443) {
    return `https://${host}`;
  }
  if ([3000, 8000, 9090].includes(port.port)) {
    return `http://${host}:${port.port}`;
  }
  return null;
}

function detectExporters(state: LoadState) {
  const processes = (state.network?.listening_ports ?? []).map((port) => `${port.process ?? ''} ${port.port}`).join(' ').toLowerCase();
  const containers = (state.docker?.containers ?? []).map((container) => `${container.name} ${container.image}`).join(' ').toLowerCase();
  return {
    node: processes.includes('9100') || containers.includes('node-exporter') || containers.includes('node_exporter'),
    promtail: containers.includes('promtail') || processes.includes('promtail'),
    cadvisor: containers.includes('cadvisor') || processes.includes('8080'),
  };
}

```

## frontend/src/features/workflows/types/workflow.ts

```typescript
export type WorkflowStatus = 'pending' | 'queued' | 'running' | 'success' | 'failed' | 'cancelled';

export type WorkflowStepStatus = 'pending' | 'running' | 'success' | 'failed' | 'skipped';

export type WorkflowStep = {
  id: string;
  workflow_run_id: string;
  step_order: number;
  step_type: string;
  name: string;
  status: WorkflowStepStatus;
  started_at: string | null;
  finished_at: string | null;
  log_output: string;
  error_output: string;
  metadata_json: Record<string, unknown>;
  target_hostname: string | null;
  created_at: string;
  updated_at: string;
};

export type WorkflowRun = {
  id: string;
  workflow_type: string;
  status: WorkflowStatus;
  trigger_source: string;
  started_at: string | null;
  finished_at: string | null;
  target_server_id: string | null;
  target_hostname: string | null;
  initiated_by: string | null;
  context_json: Record<string, unknown>;
  result_summary: Record<string, unknown>;
  error_message: string | null;
  steps: WorkflowStep[];
  current_step: string | null;
  completed_steps: number;
  failed_steps: number;
  duration_seconds: number | null;
  target_nodes: string[];
  linked_job_ids: string[];
  created_at: string;
  updated_at: string;
};

```

## frontend/src/features/deployments/types/deployment.ts

```typescript
import type { Job } from '../../jobs/types/job';

export type DeploymentStatus =
  | 'draft'
  | 'queued'
  | 'deploying'
  | 'running'
  | 'success'
  | 'partial_success'
  | 'degraded'
  | 'stopped'
  | 'failed'
  | 'cancelled'
  | 'created'
  | 'deployed';

export type DeploymentTargetExecution = {
  id: string;
  execution_id: string;
  deployment_id: string;
  target_id: string;
  server_id: string;
  hostname: string | null;
  status: DeploymentStatus;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  job_id: string | null;
  revision_id: string | null;
  stdout: string | null;
  stderr: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type DeploymentExecution = {
  id: string;
  deployment_id: string;
  operation: string;
  status: DeploymentStatus;
  trigger_source: string;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  target_count: number;
  success_count: number;
  failed_count: number;
  result_summary: Record<string, unknown>;
  error_message: string | null;
  target_executions: DeploymentTargetExecution[];
  created_at: string;
  updated_at: string;
};

export type DeploymentTarget = {
  id: string;
  server_id: string;
  hostname: string | null;
  node_type: string | null;
  environment: string | null;
  provider: string | null;
  readiness: string;
  remote_path: string;
  status: DeploymentStatus;
  last_job_id: string | null;
  last_execution: DeploymentTargetExecution | null;
  created_at: string;
  updated_at: string;
};

export type Deployment = {
  id: string;
  name: string;
  description: string | null;
  compose_content: string;
  env_content: string | null;
  credential_refs: Record<string, string>;
  status: DeploymentStatus;
  target_server_id: string | null;
  target_server_ids?: string[];
  target_hostname: string | null;
  targets: DeploymentTarget[];
  latest_execution: DeploymentExecution | null;
  execution_history: DeploymentExecution[];
  remote_path: string | null;
  ports: string[];
  compose_source: string;
  uptime_seconds: number | null;
  health_state: string;
  sync_status: string;
  created_at: string;
  updated_at: string;
};

export type CreateDeploymentPayload = {
  name: string;
  description?: string | null;
  target_server_id: string;
  target_server_ids?: string[];
  compose_content: string;
  env_content?: string | null;
  credential_refs?: Record<string, string>;
  remote_path?: string;
};

export type UpdateDeploymentPayload = CreateDeploymentPayload;

export type DeploymentOperation = {
  deployment: Deployment;
  job: Job | null;
  revision?: unknown | null;
  jobs: Job[];
  revisions?: unknown[];
  execution: DeploymentExecution | null;
};

export type DeploymentLogs = {
  deployment_id: string;
  target_server_id: string;
  logs: string;
  job: Job | null;
  jobs: Job[];
};

export type DeploymentStatusResult = {
  deployment_id: string;
  target_server_id: string | null;
  job: Job | null;
  jobs: Job[];
};

```

## frontend/src/features/deployments/DeploymentsPage.tsx

```tsx
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  Eye,
  FileText,
  KeyRound,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  RotateCw,
  Server,
  Square,
  Terminal,
  Trash2,
  X,
} from 'lucide-react';

import { PageHeader } from '../../components/layout/PageHeader';
import { PageActionButton, RuntimeBadge, CollapsibleSection } from '../../components/operations/OperationalComponents';
import { getApiErrorMessage } from '../../lib/api/client';
import { listCredentials } from '../credentials/api/credentialsApi';
import type { Credential } from '../credentials/types/credential';
import { listServers } from '../inventory/api/serversApi';
import { TargetSelector } from '../inventory/components/TargetSelector';
import { useTargetSelection } from '../inventory/hooks/useTargetSelection';
import type { Server as InventoryServer } from '../inventory/types/server';
import { selectedTargetIds } from '../inventory/types/targetSelection';
import type { Job } from '../jobs/types/job';
import {
  createDeployment,
  deleteDeployment,
  getDeploymentLogs,
  getDeploymentStatus,
  listDeployments,
  runDeploymentOperation,
  updateDeployment,
} from './api/deploymentsApi';
import type { CreateDeploymentPayload, Deployment, DeploymentStatus } from './types/deployment';

const defaultCompose = `services:
  web:
    image: nginx:alpine
    ports:
      - "8080:80"
`;

const defaultRemotePath = '/opt/nexusops/deployments';
const statusFilters: Array<DeploymentStatus | 'all'> = [
  'all',
  'running',
  'deploying',
  'partial_success',
  'degraded',
  'stopped',
  'failed',
  'draft',
];

type DrawerMode = 'create' | 'edit' | null;
type DeploymentOperationName = 'deploy' | 'redeploy' | 'restart' | 'stop';

export function DeploymentsPage() {
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [servers, setServers] = useState<InventoryServer[]>([]);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [selectedDeploymentId, setSelectedDeploymentId] = useState('');
  const [drawerMode, setDrawerMode] = useState<DrawerMode>(null);
  const [statusFilter, setStatusFilter] = useState<DeploymentStatus | 'all'>('all');
  const [name, setName] = useState('nginx-demo');
  const [targetServerId, setTargetServerId] = useState('');
  const targetSelector = useTargetSelection('single');
  const [composeContent, setComposeContent] = useState(defaultCompose);
  const [envContent, setEnvContent] = useState('');
  const [remotePath, setRemotePath] = useState(defaultRemotePath);
  const [credentialRefs, setCredentialRefs] = useState<
    Array<{ key: string; credentialId: string }>
  >([]);
  const [logs, setLogs] = useState('');
  const [inspectOutput, setInspectOutput] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isWorking, setIsWorking] = useState(false);
  const [editingDeploymentId, setEditingDeploymentId] = useState<string | null>(null);

  const selectedDeployment =
    deployments.find((deployment) => deployment.id === selectedDeploymentId) ??
    deployments[0] ??
    null;
  const filteredDeployments = useMemo(
    () =>
      deployments.filter(
        (deployment) =>
          statusFilter === 'all' || normalizeStatus(deployment.status) === statusFilter,
      ),
    [deployments, statusFilter],
  );

  async function refresh() {
    setIsLoading(true);
    setError(null);
    try {
      const [nextDeployments, nextServers, nextCredentials] = await Promise.all([
        listDeployments(),
        listServers(),
        listCredentials(),
      ]);
      setDeployments(nextDeployments);
      setServers(nextServers);
      setCredentials(nextCredentials);
      setTargetServerId((current) => current || nextServers[0]?.id || '');
      setSelectedDeploymentId((current) => current || nextDeployments[0]?.id || '');
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsLoading(false);
    }
  }

  function deploymentPayload(targets: string[]): CreateDeploymentPayload {
    return {
      name: name.trim(),
      target_server_id: targets[0],
      target_server_ids: targets,
      compose_content: composeContent,
      env_content: envContent || null,
      remote_path: remotePath.trim(),
      credential_refs: Object.fromEntries(
        credentialRefs
          .filter((item) => item.key.trim() && item.credentialId)
          .map((item) => [item.key.trim(), item.credentialId]),
      ),
    };
  }

  function resetForm() {
    setEditingDeploymentId(null);
    setName('nginx-demo');
    setComposeContent(defaultCompose);
    setEnvContent('');
    setRemotePath(defaultRemotePath);
    setCredentialRefs([]);
    targetSelector.setMode('single');
    targetSelector.setSelectedId(targetServerId);
    targetSelector.setSelectedIds([]);
  }

  function openCreateDrawer() {
    resetForm();
    setDrawerMode('create');
  }

  function openEditDrawer(deployment: Deployment) {
    setEditingDeploymentId(deployment.id);
    setSelectedDeploymentId(deployment.id);
    setName(deployment.name);
    setComposeContent(deployment.compose_content);
    setEnvContent(deployment.env_content ?? '');
    setRemotePath(deployment.remote_path ?? defaultRemotePath);
    setCredentialRefs(
      Object.entries(deployment.credential_refs ?? {}).map(([key, credentialId]) => ({
        key,
        credentialId,
      })),
    );
    targetSelector.setMode((deployment.target_server_ids?.length ?? 0) > 1 ? 'bulk' : 'single');
    targetSelector.setSelectedId(deployment.target_server_id ?? '');
    targetSelector.setSelectedIds(deployment.target_server_ids ?? []);
    setTargetServerId(deployment.target_server_id ?? '');
    setDrawerMode('edit');
    setError(null);
  }

  async function handleSave() {
    const targets = selectedTargetIds({
      ...targetSelector.selection,
      selectedId: targetSelector.selection.selectedId || targetServerId,
    });
    if (!name.trim() || targets.length === 0 || !composeContent.trim() || !remotePath.trim()) {
      setError('Deployment name, target, compose YAML, and remote path are required.');
      return;
    }
    setIsWorking(true);
    setError(null);
    try {
      const payload = deploymentPayload(targets);
      if (editingDeploymentId) {
        const deployment = await updateDeployment(editingDeploymentId, payload);
        setDeployments((current) =>
          current.map((item) => (item.id === deployment.id ? deployment : item)),
        );
        setSelectedDeploymentId(deployment.id);
      } else {
        const deployment = await createDeployment(payload);
        setDeployments((current) => [deployment, ...current]);
        setSelectedDeploymentId(deployment.id);
      }
      setDrawerMode(null);
      resetForm();
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function run(deployment: Deployment, operation: DeploymentOperationName) {
    setSelectedDeploymentId(deployment.id);
    setIsWorking(true);
    setError(null);
    try {
      const result = await runDeploymentOperation(deployment.id, operation);
      setDeployments((current) =>
        current.map((item) => (item.id === result.deployment.id ? result.deployment : item)),
      );
      setLogs(formatJobsOutput(result.jobs.length ? result.jobs : result.job ? [result.job] : []));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function inspect(deployment: Deployment) {
    setSelectedDeploymentId(deployment.id);
    setIsWorking(true);
    setError(null);
    try {
      const result = await getDeploymentStatus(deployment.id);
      setInspectOutput(formatJobsOutput(result.jobs.length ? result.jobs : result.job ? [result.job] : []));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function loadLogs(deployment: Deployment) {
    setSelectedDeploymentId(deployment.id);
    setIsWorking(true);
    setError(null);
    try {
      const result = await getDeploymentLogs(deployment.id);
      setLogs(result.logs || formatJobsOutput(result.jobs.length ? result.jobs : result.job ? [result.job] : []));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function handleDeleteDeployment(deployment: Deployment) {
    const confirmed = window.confirm(
      `Delete deployment ${deployment.name}? This removes the NexusOps record and history only. It does not stop containers or remove files from the server.`,
    );
    if (!confirmed) return;
    setIsWorking(true);
    setError(null);
    try {
      await deleteDeployment(deployment.id);
      const nextDeployments = deployments.filter((item) => item.id !== deployment.id);
      setDeployments(nextDeployments);
      setSelectedDeploymentId(nextDeployments[0]?.id ?? '');
      setLogs('');
      setInspectOutput('');
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Docker Deployments"
        description="Operational Compose services deployed to inventory-managed Linux hosts."
        actions={
          <>
            <PageActionButton icon={RefreshCw} tone="secondary" onClick={() => void refresh()}>
              Refresh
            </PageActionButton>
            <PageActionButton icon={Plus} onClick={openCreateDrawer}>
              Create deployment
            </PageActionButton>
          </>
        }
      />

      {error ? (
        <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <section className="rounded-md border border-zinc-200 bg-white p-4 shadow-sm">
        <div className="grid gap-3 sm:grid-cols-4">
          <Metric label="Services" value={deployments.length} />
          <Metric
            label="Running"
            value={deployments.filter((item) => normalizeStatus(item.status) === 'running').length}
          />
          <Metric
            label="Failed"
            value={deployments.filter((item) => normalizeStatus(item.status) === 'failed').length}
          />
          <Metric
            label="Drift"
            value={deployments.filter((item) => item.sync_status !== 'synced').length}
          />
        </div>
      </section>

      <section className="flex flex-wrap gap-2">
        {statusFilters.map((status) => (
          <button
            key={status}
            className={`rounded-md px-3 py-2 text-sm font-semibold ${statusFilter === status ? 'bg-zinc-950 text-white' : 'border border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50'}`}
            type="button"
            onClick={() => setStatusFilter(status)}
          >
            {status === 'all' ? 'All' : statusLabel(status)}
          </button>
        ))}
      </section>

      {isLoading ? (
        <div className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-500">
          Loading deployments...
        </div>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-3">
        {filteredDeployments.map((deployment) => (
          <DeploymentCard
            key={deployment.id}
            deployment={deployment}
            selected={deployment.id === selectedDeployment?.id}
            isWorking={isWorking}
            onSelect={() => setSelectedDeploymentId(deployment.id)}
            onRun={run}
            onInspect={inspect}
            onLogs={loadLogs}
            onEdit={openEditDrawer}
            onDelete={handleDeleteDeployment}
          />
        ))}
        {!filteredDeployments.length && !isLoading ? (
          <div className="rounded-md border border-dashed border-zinc-300 bg-white p-8 text-sm text-zinc-500 xl:col-span-3">
            No deployments match this view.
          </div>
        ) : null}
      </section>

      <CollapsibleSection
        title="Runtime output"
        description="Inspect and logs output are available on demand so the deployment list stays scannable."
      >
        <section className="grid gap-4 xl:grid-cols-2">
        <OutputPanel
          title="Inspect"
          value={inspectOutput || selectedDeploymentSummary(selectedDeployment)}
        />
        <OutputPanel title="Logs" value={logs || 'No logs loaded.'} />
        </section>
      </CollapsibleSection>

      {drawerMode ? (
        <DeploymentDrawer
          mode={drawerMode}
          servers={servers}
          credentials={credentials}
          targetSelector={targetSelector}
          name={name}
          composeContent={composeContent}
          envContent={envContent}
          remotePath={remotePath}
          credentialRefs={credentialRefs}
          isWorking={isWorking}
          onNameChange={setName}
          onComposeChange={setComposeContent}
          onEnvChange={setEnvContent}
          onRemotePathChange={setRemotePath}
          onCredentialRefsChange={setCredentialRefs}
          onTargetServerIdChange={setTargetServerId}
          onClose={() => {
            setDrawerMode(null);
            resetForm();
          }}
          onSave={() => void handleSave()}
        />
      ) : null}
    </div>
  );
}

function DeploymentCard({
  deployment,
  selected,
  isWorking,
  onSelect,
  onRun,
  onInspect,
  onLogs,
  onEdit,
  onDelete,
}: {
  deployment: Deployment;
  selected: boolean;
  isWorking: boolean;
  onSelect: () => void;
  onRun: (deployment: Deployment, operation: DeploymentOperationName) => Promise<void>;
  onInspect: (deployment: Deployment) => Promise<void>;
  onLogs: (deployment: Deployment) => Promise<void>;
  onEdit: (deployment: Deployment) => void;
  onDelete: (deployment: Deployment) => Promise<void>;
}) {
  return (
    <article
      className={`rounded-md border bg-white p-4 shadow-sm ${selected ? 'border-cyan-400 ring-1 ring-cyan-200' : 'border-zinc-200'}`}
    >
      <button className="w-full text-left" type="button" onClick={onSelect}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold text-zinc-950">{deployment.name}</h2>
            <p className="mt-1 flex items-center gap-1 text-sm text-zinc-500">
              <Server className="h-4 w-4" aria-hidden="true" />
              {deployment.targets.length > 1 ? (
                <span className="font-semibold text-zinc-700">{deployment.targets.length} targets</span>
              ) : deployment.target_server_id ? (
                <Link
                  className="font-semibold text-zinc-700 hover:text-zinc-950"
                  to={`/inventory/${deployment.target_server_id}`}
                  onClick={(event) => event.stopPropagation()}
                >
                  {deployment.target_hostname ?? 'Open host'}
                </Link>
              ) : (
                'No target'
              )}
            </p>
          </div>
          <RuntimeBadge value={deployment.status} />
        </div>
        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          <Info
            label="Ports"
            value={deployment.ports.length ? deployment.ports.join(', ') : 'none'}
          />
          <Info label="Health" value={deployment.health_state} />
          <Info label="Sync" value={deployment.sync_status} />
          <Info label="Uptime" value={formatDuration(deployment.uptime_seconds)} />
        </div>
        <DeploymentTargets deployment={deployment} />
        <DeploymentExecutionSummary deployment={deployment} />
        <div className="mt-3 flex flex-wrap gap-1.5">
          <Chip icon={FileText} label={deployment.compose_source} />
          {Object.keys(deployment.credential_refs ?? {}).length ? (
            <Chip
              icon={KeyRound}
              label={`${Object.keys(deployment.credential_refs).length} secret refs`}
            />
          ) : null}
          {deployment.remote_path ? (
            <Chip icon={Activity} label={deploymentPathPreview(deployment)} />
          ) : null}
        </div>
      </button>
      <div className="mt-4 flex flex-wrap gap-2">
        <ActionButton
          icon={Play}
          label="Start"
          disabled={isWorking}
          onClick={() => void onRun(deployment, 'deploy')}
        />
        <ActionButton
          icon={Square}
          label="Stop"
          disabled={isWorking}
          onClick={() => void onRun(deployment, 'stop')}
        />
        <ActionButton
          icon={RotateCw}
          label="Restart"
          disabled={isWorking}
          onClick={() => void onRun(deployment, 'restart')}
        />
        <ActionButton
          icon={RefreshCw}
          label="Redeploy"
          disabled={isWorking}
          onClick={() => void onRun(deployment, 'redeploy')}
        />
        <ActionButton
          icon={Eye}
          label="Inspect"
          disabled={isWorking}
          onClick={() => void onInspect(deployment)}
        />
        <ActionButton
          icon={Terminal}
          label="Logs"
          disabled={isWorking}
          onClick={() => void onLogs(deployment)}
        />
        <ActionButton
          icon={Pencil}
          label="Edit"
          disabled={isWorking}
          onClick={() => onEdit(deployment)}
        />
        <ActionButton
          icon={Trash2}
          label="Delete"
          disabled={isWorking}
          tone="danger"
          onClick={() => void onDelete(deployment)}
        />
      </div>
    </article>
  );
}

function DeploymentTargets({ deployment }: { deployment: Deployment }) {
  const targets = deployment.targets.length
    ? deployment.targets
    : deployment.target_server_id
      ? [
          {
            id: deployment.target_server_id,
            server_id: deployment.target_server_id,
            hostname: deployment.target_hostname,
            node_type: null,
            environment: null,
            provider: null,
            readiness: 'unknown',
            remote_path: deployment.remote_path ?? '',
            status: deployment.status,
            last_job_id: null,
            last_execution: null,
            created_at: deployment.created_at,
            updated_at: deployment.updated_at,
          },
        ]
      : [];

  if (!targets.length) {
    return <p className="mt-3 text-sm text-zinc-500">No deployment targets configured.</p>;
  }

  return (
    <div className="mt-4 grid gap-2">
      {targets.map((target) => (
        <div key={target.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2">
          <div>
            <Link
              className="text-sm font-semibold text-zinc-950 hover:text-zinc-700"
              to={`/inventory/${target.server_id}`}
              onClick={(event) => event.stopPropagation()}
            >
              {target.hostname ?? target.server_id}
            </Link>
            <p className="mt-0.5 text-xs text-zinc-500">
              {formatNodeType(target.node_type)} - {target.environment ?? 'unknown'} - {target.provider ?? 'unknown'} - {formatLabel(target.readiness)}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <RuntimeBadge value={target.status} />
            <span className="text-xs text-zinc-500">{formatDuration(target.last_execution?.duration_seconds ?? null)}</span>
          </div>
          {target.last_execution?.error_message ? (
            <p className="basis-full text-xs text-rose-700">{target.last_execution.error_message}</p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function DeploymentExecutionSummary({ deployment }: { deployment: Deployment }) {
  const execution = deployment.latest_execution;
  if (!execution) {
    return <p className="mt-3 text-sm text-zinc-500">No deployment executions yet.</p>;
  }
  return (
    <div className="mt-3 rounded-md border border-zinc-200 px-3 py-2 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-semibold text-zinc-950">{formatLabel(execution.operation)} execution</span>
        <RuntimeBadge value={execution.status} />
      </div>
      <p className="mt-1 text-xs text-zinc-500">
        {execution.success_count}/{execution.target_count} succeeded
        {execution.failed_count ? `, ${execution.failed_count} failed` : ''} - {formatDuration(execution.duration_seconds)}
      </p>
      {execution.error_message ? <p className="mt-1 text-xs text-rose-700">{execution.error_message}</p> : null}
    </div>
  );
}

function DeploymentDrawer({
  mode,
  servers,
  credentials,
  targetSelector,
  name,
  composeContent,
  envContent,
  remotePath,
  credentialRefs,
  isWorking,
  onNameChange,
  onComposeChange,
  onEnvChange,
  onRemotePathChange,
  onCredentialRefsChange,
  onTargetServerIdChange,
  onClose,
  onSave,
}: {
  mode: 'create' | 'edit';
  servers: InventoryServer[];
  credentials: Credential[];
  targetSelector: ReturnType<typeof useTargetSelection>;
  name: string;
  composeContent: string;
  envContent: string;
  remotePath: string;
  credentialRefs: Array<{ key: string; credentialId: string }>;
  isWorking: boolean;
  onNameChange: (value: string) => void;
  onComposeChange: (value: string) => void;
  onEnvChange: (value: string) => void;
  onRemotePathChange: (value: string) => void;
  onCredentialRefsChange: (value: Array<{ key: string; credentialId: string }>) => void;
  onTargetServerIdChange: (value: string) => void;
  onClose: () => void;
  onSave: () => void;
}) {
  return (
    <div className="fixed inset-0 z-40 overflow-hidden bg-zinc-950/40 p-3 sm:p-5">
      <aside className="mx-auto flex h-full w-[min(100%,56rem)] max-w-[calc(100vw-1.5rem)] flex-col overflow-hidden rounded-md bg-white shadow-xl sm:max-w-[calc(100vw-2.5rem)]">
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-zinc-200 p-5">
          <div>
            <h2 className="text-lg font-semibold text-zinc-950">
              {mode === 'edit' ? 'Edit deployment' : 'Create deployment'}
            </h2>
            <p className="mt-1 text-sm text-zinc-500">
              Compose content, target host, and runtime secrets stay in the existing deployment
              workflow.
            </p>
          </div>
          <button
            className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-zinc-300 text-zinc-600 hover:bg-zinc-50"
            type="button"
            onClick={onClose}
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
        <div className="grid min-w-0 flex-1 gap-4 overflow-y-auto overflow-x-hidden p-5">
          <label className="block">
            <span className="text-sm font-medium text-zinc-950">Deployment name</span>
            <input
              className="mt-2 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm"
              value={name}
              onChange={(event) => onNameChange(event.target.value)}
            />
          </label>
          <div className="min-w-0">
            <TargetSelector
              servers={servers}
              eligibility="deployments"
              selection={targetSelector.selection}
              filters={targetSelector.filters}
              title="Deployment target"
              description="Select the inventory host that will run this Compose service."
              onFiltersChange={targetSelector.setFilters}
              onSelectionChange={(selection) => {
                targetSelector.setMode(selection.mode);
                targetSelector.setSelectedId(selection.selectedId);
                targetSelector.setSelectedIds(selection.selectedIds);
                onTargetServerIdChange(selection.selectedId);
              }}
            />
          </div>
          <label className="block">
            <span className="text-sm font-medium text-zinc-950">Compose YAML</span>
            <textarea
              className="mt-2 min-h-72 w-full rounded-md border border-zinc-300 p-3 font-mono text-sm"
              value={composeContent}
              onChange={(event) => onComposeChange(event.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-zinc-950">Remote base path</span>
            <input
              className="mt-2 h-10 w-full rounded-md border border-zinc-300 px-3 font-mono text-sm"
              placeholder={defaultRemotePath}
              value={remotePath}
              onChange={(event) => onRemotePathChange(event.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-zinc-950">Environment file</span>
            <textarea
              className="mt-2 min-h-28 w-full rounded-md border border-zinc-300 p-3 font-mono text-sm"
              value={envContent}
              onChange={(event) => onEnvChange(event.target.value)}
            />
          </label>
          <section className="space-y-3 rounded-md border border-zinc-200 bg-zinc-50 p-4">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-medium text-zinc-950">Credential-backed env</span>
              <button
                className="inline-flex items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
                type="button"
                onClick={() =>
                  onCredentialRefsChange([
                    ...credentialRefs,
                    { key: '', credentialId: credentials[0]?.id ?? '' },
                  ])
                }
              >
                <Plus className="h-4 w-4" aria-hidden="true" />
                Add secret
              </button>
            </div>
            {credentialRefs.length ? (
              <div className="space-y-2">
                {credentialRefs.map((item, index) => (
                  <div key={index} className="grid gap-2 md:grid-cols-[1fr_1fr_auto]">
                    <input
                      className="h-10 rounded-md border border-zinc-300 px-3 font-mono text-sm"
                      placeholder="ENV_KEY"
                      value={item.key}
                      onChange={(event) =>
                        onCredentialRefsChange(
                          credentialRefs.map((row, rowIndex) =>
                            rowIndex === index ? { ...row, key: event.target.value } : row,
                          ),
                        )
                      }
                    />
                    <select
                      className="h-10 rounded-md border border-zinc-300 px-3 text-sm"
                      value={item.credentialId}
                      onChange={(event) =>
                        onCredentialRefsChange(
                          credentialRefs.map((row, rowIndex) =>
                            rowIndex === index ? { ...row, credentialId: event.target.value } : row,
                          ),
                        )
                      }
                    >
                      <option value="">Select credential</option>
                      {credentials.map((credential) => (
                        <option key={credential.id} value={credential.id}>
                          {credential.name}
                        </option>
                      ))}
                    </select>
                    <button
                      className="inline-flex h-10 items-center justify-center rounded-md border border-rose-300 px-3 text-rose-700 hover:bg-rose-50"
                      type="button"
                      onClick={() =>
                        onCredentialRefsChange(
                          credentialRefs.filter((_, rowIndex) => rowIndex !== index),
                        )
                      }
                    >
                      <Trash2 className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-zinc-500">
                Use credentials for tokens, passwords, and API keys that should not live in the env
                editor.
              </p>
            )}
          </section>
          <div className="flex justify-end gap-2 border-t border-zinc-200 pt-4">
            <button
              className="inline-flex h-10 items-center rounded-md border border-zinc-300 px-4 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
              type="button"
              onClick={onClose}
            >
              Cancel
            </button>
            <button
              className="inline-flex h-10 items-center rounded-md bg-zinc-950 px-4 text-sm font-semibold text-white disabled:bg-zinc-300"
              disabled={isWorking}
              type="button"
              onClick={onSave}
            >
              {mode === 'edit' ? 'Save changes' : 'Create deployment'}
            </button>
          </div>
        </div>
      </aside>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase text-zinc-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-zinc-950">{value}</p>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-zinc-50 px-3 py-2">
      <p className="text-xs font-semibold uppercase text-zinc-500">{label}</p>
      <p className="mt-1 truncate text-sm font-medium text-zinc-800">{value}</p>
    </div>
  );
}

function Chip({ icon: Icon, label }: { icon: typeof FileText; label: string }) {
  return (
    <span className="inline-flex max-w-full items-center gap-1 rounded-full bg-zinc-100 px-2 py-1 text-xs font-semibold text-zinc-700">
      <Icon className="h-3 w-3 shrink-0" aria-hidden="true" />
      <span className="truncate">{label}</span>
    </span>
  );
}

function OutputPanel({ title, value }: { title: string; value: string }) {
  return (
    <section className="rounded-md border border-zinc-200 bg-white p-4 shadow-sm">
      <h3 className="text-base font-semibold text-zinc-950">{title}</h3>
      <pre className="mt-3 max-h-96 overflow-auto rounded-md border border-zinc-800 bg-zinc-950 p-4 text-xs leading-5 text-zinc-100 shadow-inner">
        {value}
      </pre>
    </section>
  );
}

function deploymentPathPreview(deployment: Deployment): string {
  const safeName = deployment.name.toLowerCase().replace(/[^a-z0-9_-]/g, '-');
  return `${deployment.remote_path?.replace(/\/$/, '')}/${safeName}`;
}

function statusLabel(status: DeploymentStatus | 'all'): string {
  if (status === 'draft') return 'created';
  return formatLabel(status);
}

function normalizeStatus(status: DeploymentStatus): DeploymentStatus {
  if (status === 'created') return 'draft';
  if (status === 'deployed') return 'running';
  return status;
}

function ActionButton({
  icon: Icon,
  label,
  disabled,
  tone = 'default',
  onClick,
}: {
  icon: typeof Play;
  label: string;
  disabled: boolean;
  tone?: 'default' | 'danger';
  onClick: () => void;
}) {
  const className =
    tone === 'danger'
      ? 'inline-flex h-9 items-center gap-2 rounded-md border border-rose-300 px-2.5 text-xs font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-50'
      : 'inline-flex h-9 items-center gap-2 rounded-md border border-zinc-300 px-2.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 disabled:opacity-50';
  return (
    <button className={className} disabled={disabled} type="button" onClick={onClick}>
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {label}
    </button>
  );
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return 'unknown';
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

function formatLabel(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatNodeType(value: string | null): string {
  if (value === 'lxc') return 'LXC';
  if (value === 'vm') return 'VM';
  return value ? formatLabel(value) : 'Unknown';
}

function formatJobsOutput(jobs: Job[]): string {
  if (!jobs.length) return '';
  return jobs
    .map((job) =>
      [
        `===== ${job.operation_type} (${job.status}) =====`,
        job.stdout ?? '',
        job.stderr ?? '',
      ]
        .filter(Boolean)
        .join('\n'),
    )
    .join('\n\n');
}

function selectedDeploymentSummary(deployment: Deployment | null): string {
  if (!deployment) return 'Select a deployment to inspect runtime state.';
  const execution = deployment.latest_execution;
  return [
    `name: ${deployment.name}`,
    `status: ${statusLabel(normalizeStatus(deployment.status))}`,
    `targets: ${deployment.targets.length ? deployment.targets.map((target) => `${target.hostname ?? target.server_id}=${target.status}`).join(', ') : deployment.target_hostname ?? deployment.target_server_id ?? 'none'}`,
    `latest execution: ${execution ? `${execution.operation} ${execution.status} (${execution.success_count}/${execution.target_count} succeeded)` : 'none'}`,
    `ports: ${deployment.ports.length ? deployment.ports.join(', ') : 'none'}`,
    `compose source: ${deployment.compose_source}`,
    `health: ${deployment.health_state}`,
    `sync: ${deployment.sync_status}`,
    `remote path: ${deployment.remote_path ?? 'none'}`,
  ].join('\n');
}

```

## frontend/src/features/jobs/utils/format.ts

```typescript
import type { JobStatus } from '../types/job';

export function formatDateTime(value: string | null): string {
  if (!value) {
    return 'Not started';
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

export function jobStatusLabel(status: JobStatus): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

```

## frontend/src/features/jobs/types/job.ts

```typescript
export type JobStatus = 'pending' | 'queued' | 'dispatched' | 'running' | 'completed' | 'success' | 'failed' | 'cancelled' | 'stale';

export type Job = {
  id: string;
  target_server_id: string;
  target_hostname: string | null;
  operation_type: string;
  command: string;
  status: JobStatus;
  stdout: string | null;
  stderr: string | null;
  exit_code: number | null;
  queued_at: string | null;
  dispatched_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  runtime_duration_seconds: number | null;
  execution_origin: string;
  correlation_id: string | null;
  cancellation_requested_at: string | null;
  runtime_metadata: Record<string, unknown>;
  output_events: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
};

export type ExecuteJobPayload = {
  target_server_id: string;
  command: string;
  operation_type: string;
  credential_ref?: string | null;
  max_parallel?: number;
};

export type BulkExecutionResult = {
  target_server_id: string;
  target_hostname: string | null;
  success: boolean;
  job: Job | null;
  error: string | null;
};

export type BulkExecutionResponse = {
  operation_type: string;
  success_count: number;
  failure_count: number;
  results: BulkExecutionResult[];
};

export type ExecuteJobBulkPayload = {
  target_server_ids: string[];
  command: string;
  operation_type: string;
  credential_ref?: string | null;
};

export type OperationalAction = {
  id: string;
  name: string;
  category: string;
  description: string;
  command: string;
  destructive: boolean;
  is_builtin: boolean;
};

export type ExecuteActionPayload = {
  target_server_id: string;
  action_id: string;
  credential_ref?: string | null;
};

export type CreateOperationalActionPayload = {
  id: string;
  name: string;
  category: string;
  description: string;
  command: string;
  destructive: boolean;
};

export type UpdateOperationalActionPayload = Omit<CreateOperationalActionPayload, 'id'>;

```

## frontend/src/features/workflows/api/workflowsApi.ts

```typescript
import { apiClient } from '../../../lib/api/client';
import type { WorkflowRun } from '../types/workflow';

export async function listWorkflows(filters: { targetServerId?: string } = {}): Promise<WorkflowRun[]> {
  const response = await apiClient.get<WorkflowRun[]>('/workflows', {
    params: filters.targetServerId ? { target_server_id: filters.targetServerId } : undefined,
  });
  return response.data;
}

export async function getWorkflow(workflowId: string): Promise<WorkflowRun> {
  const response = await apiClient.get<WorkflowRun>(`/workflows/${workflowId}`);
  return response.data;
}

```

## frontend/src/features/workflows/pages/WorkflowsPage.tsx

```tsx
import { useEffect, useMemo, useState } from 'react';

import { PageHeader } from '../../../components/layout/PageHeader';
import { getApiErrorMessage } from '../../../lib/api/client';
import { listWorkflows } from '../api/workflowsApi';
import type { WorkflowRun, WorkflowStatus } from '../types/workflow';

const statusStyles: Record<WorkflowStatus, string> = {
  pending: 'bg-zinc-100 text-zinc-700 ring-zinc-200',
  queued: 'bg-sky-100 text-sky-700 ring-sky-200',
  running: 'bg-amber-100 text-amber-700 ring-amber-200',
  success: 'bg-emerald-100 text-emerald-700 ring-emerald-200',
  failed: 'bg-rose-100 text-rose-700 ring-rose-200',
  cancelled: 'bg-orange-100 text-orange-700 ring-orange-200',
};

export function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<WorkflowRun[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const selectedWorkflow = useMemo(
    () => workflows.find((workflow) => workflow.id === selectedId) ?? workflows[0] ?? null,
    [selectedId, workflows],
  );

  async function refresh() {
    setIsLoading(true);
    setError(null);
    try {
      const nextWorkflows = await listWorkflows();
      setWorkflows(nextWorkflows);
      setSelectedId((current) => current || nextWorkflows[0]?.id || '');
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader title="Workflows" description="Persistent orchestration runs, timelines, logs, and background execution state." />
      {error ? <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}

      <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
        <div className="flex items-center justify-between gap-3 border-b border-zinc-200 px-5 py-4">
          <div>
            <h3 className="text-base font-semibold text-zinc-950">Workflow runs</h3>
            <p className="mt-1 text-sm text-zinc-500">{workflows.length} runs tracked.</p>
          </div>
          <button className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50" type="button" onClick={() => void refresh()}>
            Refresh
          </button>
        </div>
        {isLoading ? <div className="m-5 h-28 animate-pulse rounded-md bg-zinc-100" /> : null}
        {!isLoading ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-zinc-200 text-sm">
              <thead className="bg-zinc-50 text-left text-xs font-semibold uppercase text-zinc-500">
                <tr>
                  <th className="px-5 py-3">Type</th>
                  <th className="px-5 py-3">Target</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Progress</th>
                  <th className="px-5 py-3">Trigger</th>
                  <th className="px-5 py-3">Jobs</th>
                  <th className="px-5 py-3">Duration</th>
                  <th className="px-5 py-3">Started</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {workflows.map((workflow) => (
                  <tr key={workflow.id} className="cursor-pointer hover:bg-zinc-50" onClick={() => setSelectedId(workflow.id)}>
                    <td className="px-5 py-3 font-medium text-zinc-950">{formatLabel(workflow.workflow_type)}</td>
                    <td className="px-5 py-3 text-zinc-600">{workflowTargetLabel(workflow)}</td>
                    <td className="px-5 py-3"><WorkflowBadge status={workflow.status} /></td>
                    <td className="px-5 py-3 text-zinc-600">{workflowProgress(workflow)}</td>
                    <td className="px-5 py-3 text-zinc-600">{formatLabel(workflow.trigger_source)}</td>
                    <td className="px-5 py-3 text-zinc-600">{workflow.linked_job_ids.length}</td>
                    <td className="px-5 py-3 text-zinc-600">{durationSeconds(workflow.duration_seconds, workflow.started_at, workflow.finished_at)}</td>
                    <td className="px-5 py-3 text-zinc-600">{formatDate(workflow.started_at ?? workflow.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {workflows.length === 0 ? <p className="p-5 text-sm text-zinc-500">No workflows have run yet.</p> : null}
          </div>
        ) : null}
      </section>

      <WorkflowDetail workflow={selectedWorkflow} />
    </div>
  );
}

function WorkflowDetail({ workflow }: { workflow: WorkflowRun | null }) {
  if (!workflow) {
    return null;
  }
  return (
    <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
      <div className="border-b border-zinc-200 px-5 py-4">
        <div className="flex flex-wrap items-center gap-3">
          <h3 className="text-base font-semibold text-zinc-950">{formatLabel(workflow.workflow_type)}</h3>
          <WorkflowBadge status={workflow.status} />
        </div>
        <div className="mt-3 grid gap-3 text-sm text-zinc-600 md:grid-cols-4">
          <RuntimeInfo label="Target" value={workflowTargetLabel(workflow)} />
          <RuntimeInfo label="Progress" value={workflowProgress(workflow)} />
          <RuntimeInfo label="Current step" value={workflow.current_step ?? 'None'} />
          <RuntimeInfo label="Linked jobs" value={workflow.linked_job_ids.length ? workflow.linked_job_ids.join(', ') : 'None'} />
        </div>
        {workflow.error_message ? <p className="mt-2 text-sm text-rose-700">{workflow.error_message}</p> : null}
      </div>
      <ol className="divide-y divide-zinc-100">
        {workflow.steps.map((step) => (
          <li key={step.id} className="p-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-sm font-semibold text-zinc-950">{step.step_order}. {stepTitle(step)}</p>
                <p className="mt-1 text-xs text-zinc-500">{formatLabel(step.step_type)} - {durationSeconds(null, step.started_at, step.finished_at)}</p>
              </div>
              <span className="rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-semibold text-zinc-700">{step.status}</span>
            </div>
            <pre className="mt-3 max-h-44 overflow-auto rounded-md bg-zinc-950 p-3 text-xs leading-5 text-zinc-50">
              {step.log_output || step.error_output || '(no logs)'}
            </pre>
          </li>
        ))}
        {workflow.steps.length === 0 ? <li className="p-5 text-sm text-zinc-500">No steps have been persisted for this workflow yet.</li> : null}
      </ol>
    </section>
  );
}

function WorkflowBadge({ status }: { status: WorkflowStatus }) {
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${statusStyles[status]}`}>
      {status}
    </span>
  );
}

function RuntimeInfo({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-zinc-50 px-3 py-2">
      <div className="text-xs font-semibold uppercase text-zinc-500">{label}</div>
      <div className="mt-1 break-words font-semibold text-zinc-900">{value}</div>
    </div>
  );
}

function formatLabel(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString() : 'Not started';
}

function workflowTargetLabel(workflow: WorkflowRun): string {
  if (workflow.target_nodes.length) {
    return workflow.target_nodes.join(', ');
  }
  if (workflow.target_hostname) {
    return workflow.target_hostname;
  }
  const stepHosts = Array.from(new Set(workflow.steps.map((step) => step.target_hostname).filter(Boolean)));
  if (stepHosts.length === 1) {
    return stepHosts[0] ?? 'Unknown target';
  }
  if (stepHosts.length > 1) {
    return `${stepHosts.length} hosts`;
  }
  return workflow.target_server_id ?? 'Multiple/unknown';
}

function workflowProgress(workflow: WorkflowRun): string {
  const total = workflow.steps.length;
  if (!total) {
    return 'No steps';
  }
  const failed = workflow.failed_steps ? `, ${workflow.failed_steps} failed` : '';
  return `${workflow.completed_steps}/${total} completed${failed}`;
}

function stepTitle(step: WorkflowRun['steps'][number]): string {
  if (!step.target_hostname) {
    return step.name;
  }
  const targetId = typeof step.metadata_json.target_server_id === 'string' ? step.metadata_json.target_server_id : '';
  return targetId ? step.name.replace(targetId, step.target_hostname) : `${step.name} on ${step.target_hostname}`;
}

function durationSeconds(value: number | null, startedAt: string | null, finishedAt: string | null): string {
  if (value != null) {
    if (value < 60) return `${value}s`;
    return `${Math.floor(value / 60)}m ${value % 60}s`;
  }
  if (!startedAt) return 'Not started';
  const end = finishedAt ? new Date(finishedAt).getTime() : Date.now();
  const seconds = Math.max(0, Math.round((end - new Date(startedAt).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

```

## frontend/src/features/jobs/JobsPage.tsx

```tsx
import { useCallback, useEffect, useMemo, useState } from 'react';

import { ContextDrawer } from '../../components/ContextDrawer';
import { PageHeader } from '../../components/layout/PageHeader';
import { CollapsibleSection, PageActionButton } from '../../components/operations/OperationalComponents';
import { getApiErrorMessage } from '../../lib/api/client';
import { listServers } from '../inventory/api/serversApi';
import type { Server } from '../inventory/types/server';
import {
  createOperationalAction,
  deleteOperationalAction,
  executeJob,
  executeJobBulk,
  executeOperationalAction,
  listJobs,
  listOperationalActions,
  updateOperationalAction,
} from './api/jobsApi';
import { JobResultViewer } from './components/JobResultViewer';
import { JobsTable } from './components/JobsTable';
import { OperationalActionsPanel } from './components/OperationalActionsPanel';
import { RunCommandPanel } from './components/RunCommandPanel';
import type { CreateOperationalActionPayload, Job, OperationalAction } from './types/job';

type ActionFormState = CreateOperationalActionPayload;

const initialActionForm: ActionFormState = {
  id: '',
  name: '',
  category: 'Custom',
  description: '',
  command: '',
  destructive: false,
};

export function JobsPage() {
  const [servers, setServers] = useState<Server[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [actions, setActions] = useState<OperationalAction[]>([]);
  const [selectedServerId, setSelectedServerId] = useState('');
  const [selectedServerIds, setSelectedServerIds] = useState<string[]>([]);
  const [selectedActionId, setSelectedActionId] = useState('');
  const [operationType, setOperationType] = useState('command');
  const [command, setCommand] = useState('uptime');
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isExecuting, setIsExecuting] = useState(false);
  const [isExecutingAction, setIsExecutingAction] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [executeError, setExecuteError] = useState<string | null>(null);
  const [bulkResult, setBulkResult] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionForm, setActionForm] = useState<ActionFormState>(initialActionForm);
  const [editingActionId, setEditingActionId] = useState<string | null>(null);
  const [isSavingAction, setIsSavingAction] = useState(false);
  const [isActionBuilderOpen, setIsActionBuilderOpen] = useState(false);

  const selectedJob = useMemo(
    () => jobs.find((job) => job.id === selectedJobId) ?? jobs[0] ?? null,
    [jobs, selectedJobId],
  );

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);

    try {
      const [nextServers, nextJobs, nextActions] = await Promise.all([
        listServers(),
        listJobs(),
        listOperationalActions(),
      ]);
      setServers(nextServers);
      setJobs(nextJobs);
      setActions(nextActions);
      setSelectedServerId((current) => current || nextServers[0]?.id || '');
      setSelectedActionId((current) => current || nextActions[0]?.id || '');
    } catch (error) {
      setLoadError(getApiErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }, []);

  async function handleExecute() {
    if ((!selectedServerId && selectedServerIds.length === 0) || !command.trim()) {
      return;
    }

    setIsExecuting(true);
    setExecuteError(null);

    try {
      if (selectedServerIds.length > 0) {
        const result = await executeJobBulk({
          target_server_ids: selectedServerIds,
          operation_type: operationType,
          command,
        });
        const resultJobs = result.results.flatMap((item) => (item.job ? [item.job] : []));
        setJobs((currentJobs) => [...resultJobs, ...currentJobs]);
        setSelectedJobId(resultJobs[0]?.id ?? null);
        setBulkResult(`${result.success_count} succeeded, ${result.failure_count} failed`);
      } else {
        const job = await executeJob({
          target_server_id: selectedServerId,
          operation_type: operationType,
          command,
        });
        setJobs((currentJobs) => [job, ...currentJobs]);
        setSelectedJobId(job.id);
        setBulkResult(null);
      }
    } catch (error) {
      setExecuteError(getApiErrorMessage(error));
    } finally {
      setIsExecuting(false);
    }
  }

  async function handleExecuteAction() {
    if (!selectedServerId || !selectedActionId) {
      return;
    }

    const action = actions.find((candidate) => candidate.id === selectedActionId);
    if (action?.destructive) {
      const confirmed = window.confirm(`Run ${action.name} on the selected host?`);
      if (!confirmed) {
        return;
      }
    }

    setIsExecutingAction(true);
    setActionError(null);

    try {
      const job = await executeOperationalAction({
        target_server_id: selectedServerId,
        action_id: selectedActionId,
      });
      setJobs((currentJobs) => [job, ...currentJobs]);
      setSelectedJobId(job.id);
    } catch (error) {
      setActionError(getApiErrorMessage(error));
    } finally {
      setIsExecutingAction(false);
    }
  }

  function updateActionField<K extends keyof ActionFormState>(field: K, value: ActionFormState[K]) {
    setActionForm((current) => ({ ...current, [field]: value }));
    setActionError(null);
  }

  function startEditAction(action: OperationalAction) {
    if (action.is_builtin) {
      return;
    }
    setIsActionBuilderOpen(true);
    setEditingActionId(action.id);
    setActionForm({
      id: action.id,
      name: action.name,
      category: action.category,
      description: action.description,
      command: action.command,
      destructive: action.destructive,
    });
    setActionError(null);
  }

  function resetActionForm() {
    setEditingActionId(null);
    setActionForm(initialActionForm);
    setIsActionBuilderOpen(false);
  }

  async function saveAction() {
    if (!actionForm.id.trim() || !actionForm.name.trim() || !actionForm.command.trim()) {
      setActionError('Action id, name, and command are required.');
      return;
    }
    setIsSavingAction(true);
    setActionError(null);
    try {
      if (editingActionId) {
        const updated = await updateOperationalAction(editingActionId, {
          name: actionForm.name,
          category: actionForm.category,
          description: actionForm.description,
          command: actionForm.command,
          destructive: actionForm.destructive,
        });
        setActions((current) =>
          current.map((action) => (action.id === updated.id ? updated : action)),
        );
        setSelectedActionId(updated.id);
      } else {
        const created = await createOperationalAction(actionForm);
        setActions((current) => [...current, created]);
        setSelectedActionId(created.id);
      }
      resetActionForm();
    } catch (error) {
      setActionError(getApiErrorMessage(error));
    } finally {
      setIsSavingAction(false);
    }
  }

  async function removeAction(action: OperationalAction) {
    if (action.is_builtin) {
      return;
    }
    const confirmed = window.confirm(`Delete custom action ${action.name}?`);
    if (!confirmed) {
      return;
    }
    setActionError(null);
    try {
      await deleteOperationalAction(action.id);
      const nextActions = actions.filter((candidate) => candidate.id !== action.id);
      setActions(nextActions);
      setSelectedActionId((current) =>
        current === action.id ? (nextActions[0]?.id ?? '') : current,
      );
      if (editingActionId === action.id) {
        resetActionForm();
      }
    } catch (error) {
      setActionError(getApiErrorMessage(error));
    }
  }

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Jobs"
        description="Reusable operational actions, remote command execution, and orchestration history."
        actions={
          <PageActionButton tone="secondary" onClick={() => setIsActionBuilderOpen(true)}>
            Create custom action
          </PageActionButton>
        }
      />

      <CollapsibleSection
        title="Operational action runner"
        description="Run a saved action against an inventory-managed node."
        defaultOpen
      >
        <OperationalActionsPanel
          actions={actions}
          error={actionError}
          isExecuting={isExecutingAction}
          selectedActionId={selectedActionId}
          selectedServerId={selectedServerId}
          servers={servers}
          onExecute={handleExecuteAction}
          onDeleteAction={removeAction}
          onEditAction={startEditAction}
          onSelectedActionChange={setSelectedActionId}
          onSelectedServerChange={setSelectedServerId}
        />
      </CollapsibleSection>

      <ContextDrawer
        description="Save reusable command sequences and scripts that execute through Jobs."
        isOpen={isActionBuilderOpen}
        title={editingActionId ? 'Edit Custom Action' : 'Create Custom Action'}
        width="xl"
        onClose={resetActionForm}
      >
        <CustomActionBuilder
          editingActionId={editingActionId}
          form={actionForm}
          isSaving={isSavingAction}
          onCancel={resetActionForm}
          onFieldChange={updateActionField}
          onSave={saveAction}
        />
      </ContextDrawer>

      <CollapsibleSection
        title="Raw command runner"
        description="Use for direct diagnostics and one-off commands. Saved actions should be preferred for repeatable operations."
      >
        <RunCommandPanel
          command={command}
          error={executeError}
          isExecuting={isExecuting}
          operationType={operationType}
          selectedServerId={selectedServerId}
          selectedServerIds={selectedServerIds}
          servers={servers}
          onCommandChange={setCommand}
          onOperationTypeChange={setOperationType}
          onSelectedServerChange={setSelectedServerId}
          onSelectedServersChange={setSelectedServerIds}
          onSubmit={handleExecute}
        />
      </CollapsibleSection>
      {bulkResult ? (
        <p className="rounded-md bg-zinc-100 px-3 py-2 text-sm text-zinc-700">{bulkResult}</p>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(480px,1fr)]">
        <JobsTable
          error={loadError}
          isLoading={isLoading}
          jobs={jobs}
          selectedJobId={selectedJob?.id ?? null}
          onRefresh={refresh}
          onSelectJob={(job) => setSelectedJobId(job.id)}
        />
        <JobResultViewer job={selectedJob} />
      </div>
    </div>
  );
}

function CustomActionBuilder({
  editingActionId,
  form,
  isSaving,
  onCancel,
  onFieldChange,
  onSave,
}: {
  editingActionId: string | null;
  form: ActionFormState;
  isSaving: boolean;
  onCancel: () => void;
  onFieldChange: <K extends keyof ActionFormState>(field: K, value: ActionFormState[K]) => void;
  onSave: () => void;
}) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-zinc-950">
            {editingActionId ? 'Edit custom action' : 'Create custom action'}
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            Save reusable command sequences and scripts that execute through Jobs.
          </p>
        </div>
        {editingActionId ? (
          <button
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
            type="button"
            onClick={onCancel}
          >
            Cancel edit
          </button>
        ) : null}
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <label className="block text-sm font-medium text-zinc-700">
          ID
          <input
            className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 font-mono text-sm disabled:bg-zinc-100"
            disabled={Boolean(editingActionId)}
            placeholder="enable-docker-user"
            value={form.id}
            onChange={(event) => onFieldChange('id', event.target.value)}
          />
        </label>
        <label className="block text-sm font-medium text-zinc-700">
          Name
          <input
            className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm"
            value={form.name}
            onChange={(event) => onFieldChange('name', event.target.value)}
          />
        </label>
        <label className="block text-sm font-medium text-zinc-700">
          Category
          <input
            className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm"
            value={form.category}
            onChange={(event) => onFieldChange('category', event.target.value)}
          />
        </label>
        <label className="flex items-end gap-2 pb-2 text-sm font-medium text-zinc-700">
          <input
            checked={form.destructive}
            type="checkbox"
            onChange={(event) => onFieldChange('destructive', event.target.checked)}
          />
          Changes host
        </label>
        <label className="block text-sm font-medium text-zinc-700 md:col-span-2 xl:col-span-4">
          Description
          <input
            className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm"
            value={form.description}
            onChange={(event) => onFieldChange('description', event.target.value)}
          />
        </label>
        <label className="block text-sm font-medium text-zinc-700 md:col-span-2 xl:col-span-4">
          Command or script
          <textarea
            className="mt-1 min-h-36 w-full rounded-md border border-zinc-300 p-3 font-mono text-sm"
            placeholder={'set -e\nsudo usermod -aG docker $USER\nid'}
            value={form.command}
            onChange={(event) => onFieldChange('command', event.target.value)}
          />
        </label>
      </div>
      <div className="mt-4 flex justify-end">
        <button
          className="rounded-md bg-zinc-950 px-4 py-2 text-sm font-semibold text-white disabled:bg-zinc-300"
          disabled={isSaving}
          type="button"
          onClick={onSave}
        >
          {isSaving ? 'Saving' : editingActionId ? 'Save action' : 'Create action'}
        </button>
      </div>
    </section>
  );
}

```

## frontend/src/features/deployments/api/deploymentsApi.ts

```typescript
import { apiClient } from '../../../lib/api/client';
import type { CreateDeploymentPayload, Deployment, DeploymentLogs, DeploymentOperation, DeploymentStatusResult, UpdateDeploymentPayload } from '../types/deployment';

export async function listDeployments(filters: { serverId?: string } = {}): Promise<Deployment[]> {
  const response = await apiClient.get<Deployment[]>('/deployments', {
    params: filters.serverId ? { server_id: filters.serverId } : undefined,
  });
  return response.data;
}

export async function createDeployment(payload: CreateDeploymentPayload): Promise<Deployment> {
  const response = await apiClient.post<Deployment>('/deployments', payload);
  return response.data;
}

export async function deleteDeployment(deploymentId: string): Promise<void> {
  await apiClient.delete(`/deployments/${deploymentId}`);
}

export async function updateDeployment(deploymentId: string, payload: UpdateDeploymentPayload): Promise<Deployment> {
  const response = await apiClient.put<Deployment>(`/deployments/${deploymentId}`, payload);
  return response.data;
}

export async function runDeploymentOperation(
  deploymentId: string,
  operation: 'deploy' | 'redeploy' | 'restart' | 'stop',
): Promise<DeploymentOperation> {
  const response = await apiClient.post<DeploymentOperation>(`/deployments/${deploymentId}/${operation}`);
  return response.data;
}

export async function getDeploymentLogs(deploymentId: string): Promise<DeploymentLogs> {
  const response = await apiClient.get<DeploymentLogs>(`/deployments/${deploymentId}/logs`);
  return response.data;
}

export async function getDeploymentStatus(deploymentId: string): Promise<DeploymentStatusResult> {
  const response = await apiClient.get<DeploymentStatusResult>(`/deployments/${deploymentId}/status`);
  return response.data;
}

```

## frontend/src/features/jobs/api/jobsApi.ts

```typescript
import { apiClient } from '../../../lib/api/client';
import type {
  BulkExecutionResponse,
  CreateOperationalActionPayload,
  ExecuteActionPayload,
  ExecuteJobBulkPayload,
  ExecuteJobPayload,
  Job,
  OperationalAction,
  UpdateOperationalActionPayload,
} from '../types/job';

export async function listJobs(filters: { targetServerId?: string } = {}): Promise<Job[]> {
  const response = await apiClient.get<Job[]>('/jobs', {
    params: filters.targetServerId ? { target_server_id: filters.targetServerId } : undefined,
  });
  return response.data;
}

export async function executeJob(payload: ExecuteJobPayload): Promise<Job> {
  const response = await apiClient.post<Job>('/jobs/execute', payload);
  return response.data;
}

export async function executeJobBulk(payload: ExecuteJobBulkPayload): Promise<BulkExecutionResponse> {
  const response = await apiClient.post<BulkExecutionResponse>('/jobs/execute/bulk', payload);
  return response.data;
}

export async function listOperationalActions(): Promise<OperationalAction[]> {
  const response = await apiClient.get<OperationalAction[]>('/jobs/actions');
  return response.data;
}

export async function executeOperationalAction(payload: ExecuteActionPayload): Promise<Job> {
  const response = await apiClient.post<Job>('/jobs/actions/execute', payload);
  return response.data;
}

export async function createOperationalAction(payload: CreateOperationalActionPayload): Promise<OperationalAction> {
  const response = await apiClient.post<OperationalAction>('/jobs/actions', payload);
  return response.data;
}

export async function updateOperationalAction(actionId: string, payload: UpdateOperationalActionPayload): Promise<OperationalAction> {
  const response = await apiClient.put<OperationalAction>(`/jobs/actions/${actionId}`, payload);
  return response.data;
}

export async function deleteOperationalAction(actionId: string): Promise<void> {
  await apiClient.delete(`/jobs/actions/${actionId}`);
}

```

## frontend/src/features/jobs/components/RunCommandPanel.tsx

```tsx
import { Play } from 'lucide-react';

import { TargetSelector } from '../../inventory/components/TargetSelector';
import { useTargetSelection } from '../../inventory/hooks/useTargetSelection';
import type { Server } from '../../inventory/types/server';

type RunCommandPanelProps = {
  command: string;
  error: string | null;
  isExecuting: boolean;
  operationType: string;
  selectedServerId: string;
  selectedServerIds: string[];
  servers: Server[];
  onCommandChange: (value: string) => void;
  onOperationTypeChange: (value: string) => void;
  onSelectedServerChange: (value: string) => void;
  onSelectedServersChange: (value: string[]) => void;
  onSubmit: () => void;
};

export function RunCommandPanel({
  command,
  error,
  isExecuting,
  operationType,
  selectedServerId,
  selectedServerIds,
  servers,
  onCommandChange,
  onOperationTypeChange,
  onSelectedServerChange,
  onSelectedServersChange,
  onSubmit,
}: RunCommandPanelProps) {
  const targetSelector = useTargetSelection(selectedServerIds.length ? 'bulk' : 'single');
  const canSubmit = Boolean((selectedServerId || selectedServerIds.length) && command.trim()) && !isExecuting;

  return (
    <section>
      <div className="mb-4">
        <TargetSelector
          servers={servers}
          selection={{
            mode: targetSelector.selection.mode,
            selectedId: selectedServerId,
            selectedIds: selectedServerIds,
          }}
          filters={targetSelector.filters}
          eligibility="jobs"
          title="Command targets"
          description="Run a raw command against one host or a selected group of hosts."
          onFiltersChange={targetSelector.setFilters}
          onSelectionChange={(nextSelection) => {
            targetSelector.setMode(nextSelection.mode);
            onSelectedServerChange(nextSelection.selectedId);
            onSelectedServersChange(nextSelection.selectedIds);
          }}
        />
      </div>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
        <div className="grid flex-1 gap-4 md:grid-cols-[1fr_160px]">
          <label className="block">
            <span className="text-sm font-medium text-zinc-950">Operation</span>
            <input
              className="mt-2 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-950 focus:ring-2 focus:ring-zinc-950/10"
              value={operationType}
              onChange={(event) => onOperationTypeChange(event.target.value)}
            />
          </label>

          <label className="block md:col-span-2">
            <span className="text-sm font-medium text-zinc-950">Command</span>
            <input
              className="mt-2 h-10 w-full rounded-md border border-zinc-300 px-3 font-mono text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-950 focus:ring-2 focus:ring-zinc-950/10"
              placeholder="uptime"
              value={command}
              onChange={(event) => onCommandChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && canSubmit) {
                  onSubmit();
                }
              }}
            />
          </label>
        </div>

        <button
          className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-zinc-950 px-4 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
          disabled={!canSubmit}
          type="button"
          onClick={onSubmit}
        >
          <Play className="h-4 w-4" aria-hidden="true" />
          {isExecuting ? 'Running' : 'Execute'}
        </button>
      </div>

      {error ? <p className="mt-4 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}
    </section>
  );
}

```

## frontend/src/features/jobs/components/OperationalActionsPanel.tsx

```tsx
import { Pencil, Play, Trash2 } from 'lucide-react';

import { TargetSelector } from '../../inventory/components/TargetSelector';
import { useTargetSelection } from '../../inventory/hooks/useTargetSelection';
import type { Server } from '../../inventory/types/server';
import type { OperationalAction } from '../types/job';

type OperationalActionsPanelProps = {
  actions: OperationalAction[];
  error: string | null;
  isExecuting: boolean;
  selectedActionId: string;
  selectedServerId: string;
  servers: Server[];
  onExecute: () => void;
  onDeleteAction: (action: OperationalAction) => void;
  onEditAction: (action: OperationalAction) => void;
  onSelectedActionChange: (value: string) => void;
  onSelectedServerChange: (value: string) => void;
};

export function OperationalActionsPanel({
  actions,
  error,
  isExecuting,
  selectedActionId,
  selectedServerId,
  servers,
  onExecute,
  onDeleteAction,
  onEditAction,
  onSelectedActionChange,
  onSelectedServerChange,
}: OperationalActionsPanelProps) {
  const targetSelector = useTargetSelection('single');
  const selectedAction = actions.find((action) => action.id === selectedActionId) ?? null;
  const groupedActions = groupActions(actions);
  const canExecute = Boolean(selectedActionId && selectedServerId) && !isExecuting;

  return (
    <section>
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end">
        <div className="grid flex-1 gap-4 md:grid-cols-2">
          <div className="md:col-span-2">
            <TargetSelector
              allowBulk={false}
              servers={servers}
              selection={{ mode: 'single', selectedId: selectedServerId, selectedIds: [] }}
              filters={targetSelector.filters}
              eligibility="jobs"
              title="Action target"
              description="Operational actions run against one inventory-managed host."
              onFiltersChange={targetSelector.setFilters}
              onSelectionChange={(nextSelection) => onSelectedServerChange(nextSelection.selectedId)}
            />
          </div>

          <label className="block">
            <span className="text-sm font-medium text-zinc-950">Operational action</span>
            <select
              className="mt-2 h-10 w-full rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-950 focus:ring-2 focus:ring-zinc-950/10"
              value={selectedActionId}
              onChange={(event) => onSelectedActionChange(event.target.value)}
            >
              <option value="">Select action</option>
              {Object.entries(groupedActions).map(([category, categoryActions]) => (
                <optgroup key={category} label={category}>
                  {categoryActions.map((action) => (
                    <option key={action.id} value={action.id}>
                      {action.name}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>
        </div>

        <button
          className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-zinc-950 px-4 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
          disabled={!canExecute}
          type="button"
          onClick={onExecute}
        >
          <Play className="h-4 w-4" aria-hidden="true" />
          {isExecuting ? 'Running' : 'Run action'}
        </button>
      </div>

      {selectedAction ? (
        <div className="mt-4 rounded-md border border-zinc-200 bg-zinc-50 px-4 py-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h3 className="text-sm font-semibold text-zinc-950">{selectedAction.name}</h3>
              <p className="mt-1 text-sm text-zinc-500">{selectedAction.description}</p>
              <p className="mt-2 break-all font-mono text-xs text-zinc-700">{selectedAction.command}</p>
            </div>
            {selectedAction.destructive ? (
              <span className="inline-flex w-fit rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">
                Changes host
              </span>
            ) : null}
            {!selectedAction.is_builtin ? (
              <div className="flex shrink-0 gap-2">
                <button className="inline-flex h-9 items-center gap-2 rounded-md border border-zinc-300 px-3 text-sm font-semibold text-zinc-700 hover:bg-white" type="button" onClick={() => onEditAction(selectedAction)}>
                  <Pencil className="h-4 w-4" aria-hidden="true" />
                  Edit
                </button>
                <button className="inline-flex h-9 items-center gap-2 rounded-md border border-rose-300 px-3 text-sm font-semibold text-rose-700 hover:bg-white" type="button" onClick={() => onDeleteAction(selectedAction)}>
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                  Delete
                </button>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {error ? <p className="mt-4 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}
    </section>
  );
}

function groupActions(actions: OperationalAction[]): Record<string, OperationalAction[]> {
  return actions.reduce<Record<string, OperationalAction[]>>((groups, action) => {
    groups[action.category] = [...(groups[action.category] ?? []), action];
    return groups;
  }, {});
}

```

## frontend/src/features/jobs/components/JobStatusBadge.tsx

```tsx
import type { JobStatus } from '../types/job';
import { jobStatusLabel } from '../utils/format';

const statusClassName: Record<JobStatus, string> = {
  pending: 'border-zinc-200 bg-zinc-50 text-zinc-700',
  queued: 'border-zinc-200 bg-zinc-50 text-zinc-700',
  dispatched: 'border-cyan-200 bg-cyan-50 text-cyan-700',
  running: 'border-sky-200 bg-sky-50 text-sky-700',
  completed: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  success: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  failed: 'border-rose-200 bg-rose-50 text-rose-700',
  cancelled: 'border-amber-200 bg-amber-50 text-amber-700',
  stale: 'border-orange-200 bg-orange-50 text-orange-700',
};

export function JobStatusBadge({ status }: { status: JobStatus }) {
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${statusClassName[status]}`}>
      {jobStatusLabel(status)}
    </span>
  );
}

```

## frontend/src/features/jobs/components/JobsTable.tsx

```tsx
import { RefreshCw } from 'lucide-react';

import type { Job } from '../types/job';
import { formatDateTime } from '../utils/format';
import { JobStatusBadge } from './JobStatusBadge';

type JobsTableProps = {
  error: string | null;
  isLoading: boolean;
  jobs: Job[];
  selectedJobId: string | null;
  onRefresh: () => void;
  onSelectJob: (job: Job) => void;
};

export function JobsTable({
  error,
  isLoading,
  jobs,
  selectedJobId,
  onRefresh,
  onSelectJob,
}: JobsTableProps) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
      <div className="flex flex-col gap-3 border-b border-zinc-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-base font-semibold text-zinc-950">Job history</h3>
          <p className="mt-1 text-sm text-zinc-500">{jobs.length} executions persisted.</p>
        </div>
        <button
          className="inline-flex items-center justify-center gap-2 rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50"
          type="button"
          onClick={onRefresh}
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Refresh
        </button>
      </div>

      {error ? <p className="m-5 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}
      {isLoading ? <LoadingRows /> : null}
      {!isLoading && !error && jobs.length === 0 ? (
        <p className="p-5 text-sm text-zinc-500">No jobs have been executed yet.</p>
      ) : null}

      {!isLoading && jobs.length > 0 ? (
        <>
          <div className="hidden overflow-x-auto lg:block">
            <table className="min-w-full divide-y divide-zinc-200">
              <thead className="bg-zinc-50">
                <tr>
                  {['Target', 'Operation', 'Command', 'Status', 'Exit', 'Duration', 'Completed'].map((heading) => (
                    <th
                      key={heading}
                      className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-normal text-zinc-500"
                    >
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {jobs.map((job) => (
                  <tr
                    key={job.id}
                    className={`cursor-pointer hover:bg-zinc-50 ${
                      selectedJobId === job.id ? 'bg-zinc-50' : ''
                    }`}
                    onClick={() => onSelectJob(job)}
                  >
                    <td className="px-5 py-4 text-sm font-medium text-zinc-950">
                      {job.target_hostname ?? 'Unknown host'}
                    </td>
                    <td className="px-5 py-4 text-sm text-zinc-700">{job.operation_type}</td>
                    <td className="max-w-md truncate px-5 py-4 font-mono text-sm text-zinc-700">
                      {job.command}
                    </td>
                    <td className="px-5 py-4">
                      <JobStatusBadge status={job.status} />
                    </td>
                    <td className="px-5 py-4 text-sm text-zinc-700">
                      {job.exit_code ?? '-'}
                    </td>
                    <td className="px-5 py-4 text-sm text-zinc-700">
                      {formatDuration(job.started_at, job.completed_at)}
                    </td>
                    <td className="px-5 py-4 text-sm text-zinc-700">
                      {formatDateTime(job.completed_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="grid gap-3 p-4 lg:hidden">
            {jobs.map((job) => (
              <button
                key={job.id}
                className={`rounded-lg border p-4 text-left ${
                  selectedJobId === job.id ? 'border-zinc-950' : 'border-zinc-200'
                }`}
                type="button"
                onClick={() => onSelectJob(job)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h4 className="font-semibold text-zinc-950">
                      {job.target_hostname ?? 'Unknown host'}
                    </h4>
                    <p className="mt-1 text-sm text-zinc-500">{job.operation_type}</p>
                  </div>
                  <JobStatusBadge status={job.status} />
                </div>
                <p className="mt-3 break-all font-mono text-sm text-zinc-800">{job.command}</p>
                <p className="mt-3 text-xs text-zinc-500">{formatDateTime(job.completed_at)}</p>
              </button>
            ))}
          </div>
        </>
      ) : null}
    </section>
  );
}

function formatDuration(startedAt: string | null, completedAt: string | null): string {
  if (!startedAt || !completedAt) {
    return '-';
  }
  const seconds = Math.max(0, Math.round((new Date(completedAt).getTime() - new Date(startedAt).getTime()) / 1000));
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

function LoadingRows() {
  return (
    <div className="space-y-3 p-5">
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="h-14 animate-pulse rounded-md bg-zinc-100" />
      ))}
    </div>
  );
}

```

## frontend/src/features/jobs/components/JobResultViewer.tsx

```tsx
import { useState } from 'react';
import { Copy, Expand, WrapText } from 'lucide-react';

import type { Job } from '../types/job';
import { formatDateTime } from '../utils/format';

type OutputTab = 'stdout' | 'stderr' | 'command' | 'metadata';

export function JobResultViewer({ job }: { job: Job | null }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState<OutputTab>('stdout');
  const [wrapOutput, setWrapOutput] = useState(true);

  if (!job) {
    return (
      <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <h3 className="text-base font-semibold text-zinc-950">Execution result</h3>
        <p className="mt-2 text-sm text-zinc-500">Select a job to inspect command output.</p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
      <div className="border-b border-zinc-200 px-5 py-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-zinc-950">Execution result</h3>
            <p className="mt-1 text-sm text-zinc-500">
              Started {formatDateTime(job.started_at)} · Completed {formatDateTime(job.completed_at)} · Duration {formatDuration(job)}
            </p>
          </div>
          <button
            className="inline-flex items-center gap-2 rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
            type="button"
            onClick={() => setIsExpanded(true)}
          >
            <Expand className="h-4 w-4" aria-hidden="true" />
            Expand
          </button>
        </div>
        <p className="mt-2 truncate font-mono text-sm text-zinc-500">{job.command}</p>
      </div>

      <div className="p-5">
        <OutputInspector
          activeTab={activeTab}
          job={job}
          wrapOutput={wrapOutput}
          onTabChange={setActiveTab}
          onToggleWrap={() => setWrapOutput((current) => !current)}
        />
      </div>
      {isExpanded ? (
        <ExpandedModal
          activeTab={activeTab}
          job={job}
          wrapOutput={wrapOutput}
          onClose={() => setIsExpanded(false)}
          onTabChange={setActiveTab}
          onToggleWrap={() => setWrapOutput((current) => !current)}
        />
      ) : null}
    </section>
  );
}

function OutputInspector({
  activeTab,
  job,
  wrapOutput,
  onTabChange,
  onToggleWrap,
}: {
  activeTab: OutputTab;
  job: Job;
  wrapOutput: boolean;
  onTabChange: (tab: OutputTab) => void;
  onToggleWrap: () => void;
}) {
  const value = getTabValue(job, activeTab);

  return (
    <div className="flex h-full min-h-0 flex-col rounded-lg border border-zinc-200 bg-white">
      <div className="flex flex-col gap-3 border-b border-zinc-200 p-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex flex-wrap gap-2">
          {(['stdout', 'stderr', 'command', 'metadata'] as OutputTab[]).map((tab) => (
            <button
              key={tab}
              className={[
                'rounded-md px-3 py-1.5 text-sm font-semibold capitalize transition',
                activeTab === tab ? 'bg-zinc-950 text-white' : 'bg-zinc-100 text-zinc-700 hover:bg-zinc-200',
              ].join(' ')}
              type="button"
              onClick={() => onTabChange(tab)}
            >
              {tab}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <button
            className="inline-flex items-center gap-1 rounded-md border border-zinc-300 px-2.5 py-1.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
            type="button"
            onClick={onToggleWrap}
          >
            <WrapText className="h-3.5 w-3.5" aria-hidden="true" />
            {wrapOutput ? 'Wrap on' : 'Wrap off'}
          </button>
          <button
            className="inline-flex items-center gap-1 rounded-md border border-zinc-300 px-2.5 py-1.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
            type="button"
            onClick={() => void navigator.clipboard.writeText(value)}
          >
            <Copy className="h-3.5 w-3.5" aria-hidden="true" />
            Copy
          </button>
        </div>
      </div>
      <pre
        className={[
          'max-h-[34rem] min-h-80 flex-1 overflow-auto rounded-b-lg bg-zinc-950 p-4 text-xs leading-5 text-zinc-50',
          wrapOutput ? 'whitespace-pre-wrap break-words' : 'whitespace-pre',
        ].join(' ')}
      >
        {value.trim() || '(empty)'}
      </pre>
    </div>
  );
}

function ExpandedModal({
  activeTab,
  job,
  wrapOutput,
  onClose,
  onTabChange,
  onToggleWrap,
}: {
  activeTab: OutputTab;
  job: Job;
  wrapOutput: boolean;
  onClose: () => void;
  onTabChange: (tab: OutputTab) => void;
  onToggleWrap: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 bg-zinc-950/70 p-4">
      <div className="mx-auto flex h-full max-w-7xl flex-col rounded-lg bg-white shadow-xl">
        <div className="flex items-start justify-between gap-4 border-b border-zinc-200 px-5 py-4">
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-zinc-950">{job.operation_type}</h3>
            <p className="mt-1 truncate font-mono text-sm text-zinc-500">{job.command}</p>
            <p className="mt-2 text-sm text-zinc-500">Duration {formatDuration(job)} · Exit {job.exit_code ?? '-'}</p>
          </div>
          <button className="rounded-md bg-zinc-900 px-3 py-2 text-sm font-semibold text-white hover:bg-zinc-800" type="button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-hidden p-5">
          <OutputInspector
            activeTab={activeTab}
            job={job}
            wrapOutput={wrapOutput}
            onTabChange={onTabChange}
            onToggleWrap={onToggleWrap}
          />
        </div>
      </div>
    </div>
  );
}

function getTabValue(job: Job, tab: OutputTab): string {
  if (tab === 'stdout') {
    return job.stdout ?? '';
  }
  if (tab === 'stderr') {
    return job.stderr ?? '';
  }
  if (tab === 'command') {
    return job.command;
  }
  return [
    `Target: ${job.target_hostname ?? job.target_server_id}`,
    `Operation: ${job.operation_type}`,
    `Status: ${job.status}`,
    `Exit code: ${job.exit_code ?? '-'}`,
    `Started: ${formatDateTime(job.started_at)}`,
    `Completed: ${formatDateTime(job.completed_at)}`,
    `Duration: ${formatDuration(job)}`,
  ].join('\n');
}

function formatDuration(job: Job): string {
  if (!job.started_at || !job.completed_at) {
    return 'Unavailable';
  }
  const seconds = Math.max(0, Math.round((new Date(job.completed_at).getTime() - new Date(job.started_at).getTime()) / 1000));
  if (seconds < 60) {
    return `${seconds}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}m ${remainder}s`;
}

```

