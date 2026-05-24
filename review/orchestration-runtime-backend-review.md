# Orchestration Runtime Backend Review

Generated from the current NexusOps workspace for focused code review.

## backend/app/modules/orchestration/__init__.py

``python
"""Shared orchestration helpers for runtime-facing modules."""

````

## backend/app/modules/orchestration/activity.py

``python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class OperationalActivityRead(BaseModel):
    id: str
    source_type: str
    source_id: str
    event_type: str
    title: str
    status: str | None = None
    severity: str = "info"
    occurred_at: datetime | None = None
    message: str | None = None
    correlation_id: str | None = None
    job_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


def job_activity_timeline(job, *, target_hostname: str | None = None) -> list[OperationalActivityRead]:
    source_id = str(job.id)
    base_metadata = {
        "operation_type": job.operation_type,
        "execution_origin": job.execution_origin,
        "target_server_id": str(job.target_server_id),
        "target_hostname": target_hostname,
    }
    activities = [
        _activity(
            source_type="job",
            source_id=source_id,
            event_type="job.created",
            title="Job created",
            status="pending",
            occurred_at=job.created_at,
            correlation_id=job.correlation_id,
            metadata=base_metadata,
        )
    ]
    transitions = [
        ("job.queued", "Job queued", "queued", job.queued_at),
        ("job.dispatched", "Job dispatched", "dispatched", job.dispatched_at),
        ("job.running", "Job running", "running", job.started_at),
        ("job.completed", "Job completed", str(job.status), job.completed_at),
    ]
    for event_type, title, status, occurred_at in transitions:
        if occurred_at is None:
            continue
        activities.append(
            _activity(
                source_type="job",
                source_id=source_id,
                event_type=event_type,
                title=title,
                status=status,
                severity=_severity(status),
                occurred_at=occurred_at,
                correlation_id=job.correlation_id,
                message=_job_message(job, status),
                metadata=base_metadata,
            )
        )
    for output_event in job.output_events or []:
        stream = str(output_event.get("stream", "output"))
        activities.append(
            _activity(
                source_type="job",
                source_id=source_id,
                event_type=f"job.output.{stream}",
                title=f"{stream.upper()} output captured",
                status=str(job.status),
                severity="danger" if stream == "stderr" else "info",
                occurred_at=_parse_datetime(output_event.get("created_at")),
                correlation_id=job.correlation_id,
                message=str(output_event.get("content", "")).strip() or None,
                metadata={**base_metadata, "sequence": output_event.get("sequence")},
            )
        )
    return _sort_activities(activities)


def workflow_activity_timeline(workflow, steps) -> list[OperationalActivityRead]:
    source_id = str(workflow.id)
    activities = [
        _activity(
            source_type="workflow",
            source_id=source_id,
            event_type="workflow.created",
            title="Workflow created",
            status=str(workflow.status),
            occurred_at=workflow.created_at,
            message=workflow.error_message,
            metadata={
                "workflow_type": str(workflow.workflow_type),
                "trigger_source": str(workflow.trigger_source),
                "target_server_id": str(workflow.target_server_id) if workflow.target_server_id else None,
            },
        )
    ]
    if workflow.started_at:
        activities.append(
            _activity(
                source_type="workflow",
                source_id=source_id,
                event_type="workflow.running",
                title="Workflow started",
                status="running",
                occurred_at=workflow.started_at,
            )
        )
    for step in steps:
        metadata = dict(step.metadata_json or {})
        job_ids = [str(job_id) for job_id in metadata.get("job_ids", [])] if isinstance(metadata.get("job_ids"), list) else []
        activities.append(
            _activity(
                source_type="workflow_step",
                source_id=str(step.id),
                event_type=f"workflow.step.{step.status}",
                title=step.name,
                status=str(step.status),
                severity=_severity(str(step.status)),
                occurred_at=step.finished_at or step.started_at or step.created_at,
                message=step.error_output or step.log_output or None,
                job_ids=job_ids,
                metadata=metadata,
            )
        )
    if workflow.finished_at:
        activities.append(
            _activity(
                source_type="workflow",
                source_id=source_id,
                event_type=f"workflow.{workflow.status}",
                title="Workflow finished",
                status=str(workflow.status),
                severity=_severity(str(workflow.status)),
                occurred_at=workflow.finished_at,
                message=workflow.error_message,
                metadata=workflow.result_summary or {},
            )
        )
    return _sort_activities(activities)


def deployment_execution_activity_timeline(execution, target_executions) -> list[OperationalActivityRead]:
    source_id = str(execution.id)
    activities = [
        _activity(
            source_type="deployment_execution",
            source_id=source_id,
            event_type="deployment.execution.started",
            title=f"Deployment {execution.operation} started",
            status=str(execution.status),
            occurred_at=execution.started_at or execution.created_at,
            message=execution.error_message,
            metadata={"deployment_id": str(execution.deployment_id), "operation": execution.operation},
        )
    ]
    for target_execution in target_executions:
        activities.append(
            _activity(
                source_type="deployment_target_execution",
                source_id=str(target_execution.id),
                event_type=f"deployment.target.{target_execution.status}",
                title=f"Target {target_execution.hostname or target_execution.server_id}",
                status=str(target_execution.status),
                severity=_severity(str(target_execution.status)),
                occurred_at=target_execution.finished_at or target_execution.started_at or target_execution.created_at,
                message=target_execution.error_message or target_execution.stderr or target_execution.stdout,
                job_ids=[str(target_execution.job_id)] if target_execution.job_id else [],
                metadata={
                    "deployment_id": str(target_execution.deployment_id),
                    "server_id": str(target_execution.server_id),
                    "revision_id": str(target_execution.revision_id) if target_execution.revision_id else None,
                },
            )
        )
    if execution.finished_at:
        activities.append(
            _activity(
                source_type="deployment_execution",
                source_id=source_id,
                event_type=f"deployment.execution.{execution.status}",
                title="Deployment execution finished",
                status=str(execution.status),
                severity=_severity(str(execution.status)),
                occurred_at=execution.finished_at,
                message=execution.error_message,
                job_ids=[str(job_id) for job_id in (execution.result_summary or {}).get("job_ids", [])],
                metadata=execution.result_summary or {},
            )
        )
    return _sort_activities(activities)


def _activity(
    *,
    source_type: str,
    source_id: str,
    event_type: str,
    title: str,
    status: str | None = None,
    severity: str = "info",
    occurred_at: datetime | None = None,
    message: str | None = None,
    correlation_id: str | None = None,
    job_ids: list[str] | None = None,
    metadata: dict[str, object] | None = None,
) -> OperationalActivityRead:
    clean_metadata = {key: value for key, value in (metadata or {}).items() if value is not None}
    return OperationalActivityRead(
        id=f"{source_type}:{source_id}:{event_type}:{occurred_at.isoformat() if occurred_at else 'pending'}",
        source_type=source_type,
        source_id=source_id,
        event_type=event_type,
        title=title,
        status=status,
        severity=severity,
        occurred_at=occurred_at,
        message=_shorten(message),
        correlation_id=correlation_id,
        job_ids=job_ids or [],
        metadata=clean_metadata,
    )


def _job_message(job, status: str) -> str | None:
    if status in {"failed", "cancelled", "stale"}:
        return job.stderr or "Job did not complete successfully"
    if status in {"success", "completed"}:
        return f"Exit code {job.exit_code}" if job.exit_code is not None else None
    return None


def _severity(status: str) -> str:
    if "fail" in status or status in {"cancelled", "stale", "degraded"}:
        return "danger"
    if "partial" in status or status in {"queued", "running", "deploying", "pending"}:
        return "warning"
    if status in {"success", "completed", "running", "stopped"}:
        return "success"
    return "info"


def _sort_activities(activities: list[OperationalActivityRead]) -> list[OperationalActivityRead]:
    return sorted(activities, key=lambda item: _sort_timestamp(item.occurred_at))


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _sort_timestamp(value: datetime | None) -> float:
    if value is None:
        return 0
    normalized = value if value.tzinfo else value.replace(tzinfo=UTC)
    return normalized.timestamp()


def _shorten(value: str | None, limit: int = 500) -> str | None:
    if not value:
        return None
    clean = value.strip()
    if len(clean) <= limit:
        return clean
    return f"{clean[:limit].rstrip()}..."

````

## backend/app/modules/orchestration/semantics.py

``python
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from backend.app.modules.deployments.models import DeploymentStatus
from backend.app.modules.jobs.models import JobStatus
from backend.app.modules.workflows.models import WorkflowStatus, WorkflowStepStatus


class OrchestrationRole(StrEnum):
    JOB = "atomic_execution_unit"
    WORKFLOW = "orchestration_coordinator"
    DEPLOYMENT = "stateful_application_lifecycle"
    PROFILE = "reusable_orchestration_recipe"
    PACKAGE = "reusable_executable_definition"
    AUTOMATION = "scheduling_trigger_layer"


@dataclass(frozen=True)
class LifecycleSemantics:
    pending: set[Any]
    active: set[Any]
    success: set[Any]
    failure: set[Any]
    cancelled: set[Any]
    stale: set[Any]

    @property
    def terminal(self) -> set[Any]:
        return self.success | self.failure | self.cancelled | self.stale

    def is_terminal(self, status: Any) -> bool:
        return status in self.terminal

    def is_success(self, status: Any) -> bool:
        return status in self.success

    def is_failure(self, status: Any) -> bool:
        return status in self.failure | self.cancelled | self.stale

    def is_active(self, status: Any) -> bool:
        return status in self.active


JOB_LIFECYCLE = LifecycleSemantics(
    pending={JobStatus.PENDING},
    active={JobStatus.QUEUED, JobStatus.DISPATCHED, JobStatus.RUNNING},
    success={JobStatus.SUCCESS, JobStatus.COMPLETED},
    failure={JobStatus.FAILED},
    cancelled={JobStatus.CANCELLED},
    stale={JobStatus.STALE},
)

WORKFLOW_LIFECYCLE = LifecycleSemantics(
    pending={WorkflowStatus.PENDING},
    active={WorkflowStatus.QUEUED, WorkflowStatus.RUNNING},
    success={WorkflowStatus.SUCCESS},
    failure={WorkflowStatus.FAILED},
    cancelled={WorkflowStatus.CANCELLED},
    stale=set(),
)

WORKFLOW_STEP_LIFECYCLE = LifecycleSemantics(
    pending={WorkflowStepStatus.PENDING},
    active={WorkflowStepStatus.RUNNING},
    success={WorkflowStepStatus.SUCCESS, WorkflowStepStatus.SKIPPED},
    failure={WorkflowStepStatus.FAILED},
    cancelled=set(),
    stale=set(),
)

DEPLOYMENT_EXECUTION_LIFECYCLE = LifecycleSemantics(
    pending={DeploymentStatus.QUEUED, DeploymentStatus.DRAFT},
    active={DeploymentStatus.DEPLOYING},
    success={
        DeploymentStatus.RUNNING,
        DeploymentStatus.STOPPED,
        DeploymentStatus.SUCCESS,
        DeploymentStatus.PARTIAL_SUCCESS,
    },
    failure={DeploymentStatus.FAILED, DeploymentStatus.DEGRADED},
    cancelled={DeploymentStatus.CANCELLED},
    stale=set(),
)


def orchestration_origin(operation_type: str) -> str:
    return operation_type.split(":", 1)[0] or "manual"


def is_job_success(status: JobStatus) -> bool:
    return JOB_LIFECYCLE.is_success(status)


def is_job_failure(status: JobStatus) -> bool:
    return JOB_LIFECYCLE.is_failure(status)


def is_job_terminal(status: JobStatus) -> bool:
    return JOB_LIFECYCLE.is_terminal(status)


def job_success_states() -> set[JobStatus]:
    return set(JOB_LIFECYCLE.success)


def job_failure_states() -> set[JobStatus]:
    return JOB_LIFECYCLE.failure | JOB_LIFECYCLE.cancelled | JOB_LIFECYCLE.stale


def deployment_execution_success_states() -> set[DeploymentStatus]:
    return set(DEPLOYMENT_EXECUTION_LIFECYCLE.success)


def deployment_execution_failure_states() -> set[DeploymentStatus]:
    return DEPLOYMENT_EXECUTION_LIFECYCLE.failure | DEPLOYMENT_EXECUTION_LIFECYCLE.cancelled


def workflow_failure_states() -> set[WorkflowStatus]:
    return WORKFLOW_LIFECYCLE.failure | WORKFLOW_LIFECYCLE.cancelled | WORKFLOW_LIFECYCLE.stale


def workflow_runtime_state(status: WorkflowStatus) -> str:
    if status == WorkflowStatus.PENDING:
        return "queued"
    return status.value


def runtime_metadata(
    *,
    operation_type: str,
    execution_origin: str | None = None,
    correlation_id: str | None = None,
    target_hostname: str | None = None,
    target_server_id: str | None = None,
    transport: str | None = None,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "execution_origin": execution_origin or orchestration_origin(operation_type),
        "operation_type": operation_type,
    }
    if correlation_id:
        metadata["correlation_id"] = correlation_id
    if target_hostname:
        metadata["target_hostname"] = target_hostname
    if target_server_id:
        metadata["target_server_id"] = target_server_id
    if transport:
        metadata["transport"] = transport
    if extra:
        metadata.update(extra)
    return metadata

````

## backend/app/modules/orchestration/utils.py

``python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Iterable


@dataclass(frozen=True)
class ExecutionSummary:
    """Normalized execution counters for orchestration reads and rollups."""

    total_count: int
    success_count: int
    failed_count: int
    job_ids: list[str] = field(default_factory=list)
    failure_messages: list[str] = field(default_factory=list)

    @property
    def failure_count(self) -> int:
        return self.failed_count

    @property
    def has_failures(self) -> bool:
        return self.failed_count > 0

    @property
    def all_successful(self) -> bool:
        return self.total_count > 0 and self.success_count == self.total_count

    def as_result_summary(self) -> dict[str, Any]:
        return {
            "target_count": self.total_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "job_ids": self.job_ids,
        }


@dataclass(frozen=True)
class TargetExecutionAggregate:
    """Aggregated view of per-target execution outcomes."""

    summary: ExecutionSummary
    statuses: list[Any]


def duration_seconds(
    started_at: datetime | None,
    finished_at: datetime | None,
    *,
    default_to_now: bool = True,
) -> int | None:
    if started_at is None:
        return None
    if finished_at is None and not default_to_now:
        return None
    start = ensure_aware_utc(started_at)
    end = ensure_aware_utc(finished_at or datetime.now(UTC))
    return max(0, int((end - start).total_seconds()))


def summarize_statuses(
    items: Iterable[Any],
    *,
    success_states: set[Any],
    failure_states: set[Any],
) -> ExecutionSummary:
    values = list(items)
    return ExecutionSummary(
        total_count=len(values),
        success_count=sum(1 for item in values if status_value(item) in success_states),
        failed_count=sum(1 for item in values if status_value(item) in failure_states),
    )


def aggregate_target_executions(
    target_executions: Iterable[Any],
    *,
    success_states: set[Any],
    failure_states: set[Any],
) -> TargetExecutionAggregate:
    executions = list(target_executions)
    status_summary = summarize_statuses(
        executions,
        success_states=success_states,
        failure_states=failure_states,
    )
    summary = ExecutionSummary(
        total_count=status_summary.total_count,
        success_count=status_summary.success_count,
        failed_count=status_summary.failed_count,
        job_ids=[str(job_id) for item in executions if (job_id := getattr(item, "job_id", None))],
        failure_messages=[
            message
            for item in executions
            if (message := getattr(item, "error_message", None))
        ],
    )
    return TargetExecutionAggregate(
        summary=summary,
        statuses=[status_value(item) for item in executions],
    )


def rollup_status(
    statuses: Iterable[Any],
    *,
    success_states: set[Any],
    failure_states: set[Any],
    empty_status: Any,
    all_success_status: Any,
    partial_success_status: Any,
    all_failed_status: Any,
    mixed_status: Any,
) -> Any:
    values = list(statuses)
    if not values:
        return empty_status
    summary = summarize_statuses(
        values,
        success_states=success_states,
        failure_states=failure_states,
    )
    if summary.success_count == len(values):
        return all_success_status
    if summary.success_count and summary.failed_count:
        return partial_success_status
    if summary.failed_count == len(values):
        return all_failed_status
    return mixed_status


def success_failure_counts(
    items: Iterable[Any],
    *,
    success_attr: str = "success",
) -> tuple[int, int]:
    values = list(items)
    success_count = sum(1 for item in values if bool(getattr(item, success_attr)))
    return success_count, len(values) - success_count


def status_value(item: Any) -> Any:
    return getattr(item, "status", item)


def ensure_aware_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)

````

## backend/app/modules/jobs/runtime.py

``python
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
from backend.app.modules.orchestration.semantics import (
    JOB_LIFECYCLE,
    is_job_success,
    orchestration_origin,
    runtime_metadata,
)
from backend.app.modules.orchestration.utils import duration_seconds


TERMINAL_JOB_STATES = JOB_LIFECYCLE.terminal

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
        job.execution_origin = job.execution_origin or orchestration_origin(payload.operation_type)
        job.runtime_metadata = {
            **(job.runtime_metadata or {}),
            **runtime_metadata(
                operation_type=payload.operation_type,
                execution_origin=job.execution_origin,
                correlation_id=correlation_id,
                target_hostname=server.hostname,
                target_server_id=str(server.id),
                transport=self.ssh_adapter.name,
            ),
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
            result="success" if is_job_success(job.status) else "failed",
            metadata={
                "job_id": str(job.id),
                "operation_type": job.operation_type,
                "exit_code": job.exit_code,
                "target_hostname": server.hostname,
                "correlation_id": job.correlation_id,
                "runtime_duration_seconds": job.runtime_duration_seconds,
            },
            error=job.stderr if not is_job_success(job.status) else None,
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

````

## backend/app/modules/jobs/models.py

``python
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

````

## backend/app/modules/jobs/schemas.py

``python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.modules.jobs.models import JobStatus
from backend.app.modules.orchestration.activity import OperationalActivityRead


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
    activity_timeline: list[OperationalActivityRead] = Field(default_factory=list)
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

````

## backend/app/modules/jobs/repository.py

``python
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from backend.app.common.repository import BaseRepository
from backend.app.modules.jobs.models import CustomOperationalAction, Job


class JobRepository(BaseRepository[Job]):
    async def create(self, job: Job) -> Job:
        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def get_by_id(self, job_id: UUID) -> Job | None:
        result = await self.session.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()

    async def list(self) -> list[Job]:
        result = await self.session.execute(select(Job).order_by(Job.created_at.desc()))
        return list(result.scalars().all())

    async def list_for_target(self, target_server_id: UUID) -> list[Job]:
        result = await self.session.execute(
            select(Job)
            .where(Job.target_server_id == target_server_id)
            .order_by(Job.created_at.desc())
        )
        return list(result.scalars().all())


class CustomOperationalActionRepository(BaseRepository[CustomOperationalAction]):
    async def create(self, action: CustomOperationalAction) -> CustomOperationalAction:
        self.session.add(action)
        await self.session.flush()
        await self.session.refresh(action)
        return action

    async def get_by_slug(self, slug: str) -> CustomOperationalAction | None:
        result = await self.session.execute(select(CustomOperationalAction).where(CustomOperationalAction.slug == slug))
        return result.scalar_one_or_none()

    async def list(self) -> list[CustomOperationalAction]:
        result = await self.session.execute(
            select(CustomOperationalAction).order_by(CustomOperationalAction.category, CustomOperationalAction.name)
        )
        return list(result.scalars().all())

    async def delete(self, action: CustomOperationalAction) -> None:
        await self.session.delete(action)

````

## backend/app/modules/jobs/service.py

``python
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
from backend.app.modules.orchestration.activity import job_activity_timeline
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

        execution_origin = orchestration_origin(payload.operation_type)
        correlation_id = str(uuid4())
        job = Job(
            target_server_id=server.id,
            operation_type=payload.operation_type,
            command=payload.redacted_command or payload.command,
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

````

## backend/app/modules/jobs/router.py

``python
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.ssh import ParamikoSshAdapter
from backend.app.db.session import AsyncSessionLocal, get_db_session
from backend.app.modules.audit.repository import AuditEventRepository
from backend.app.modules.audit.service import AuditService
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.jobs.repository import JobRepository
from backend.app.modules.jobs.repository import CustomOperationalActionRepository
from backend.app.modules.jobs.schemas import (
    BulkExecutionRead,
    JobActionExecuteRequest,
    JobBulkExecuteRequest,
    JobExecuteRequest,
    JobRead,
    OperationalActionCreate,
    OperationalActionRead,
    OperationalActionUpdate,
)
from backend.app.modules.jobs.service import (
    BuiltinOperationalActionError,
    JobNotFoundError,
    JobService,
    JobTargetNotFoundError,
    JobTargetNotManagedError,
    OperationalActionConflictError,
    OperationalActionNotFoundError,
)

router = APIRouter()


async def get_job_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> JobService:
    return JobService(
        job_repository=JobRepository(session),
        server_repository=ServerRepository(session),
        ssh_adapter=ParamikoSshAdapter(),
        action_repository=CustomOperationalActionRepository(session),
        credential_service=CredentialService(repository=CredentialRepository(session)),
        audit_service=AuditService(AuditEventRepository(session)),
        session_factory=AsyncSessionLocal,
    )


@router.get("", response_model=list[JobRead])
async def list_jobs(
    service: Annotated[JobService, Depends(get_job_service)],
    target_server_id: UUID | None = None,
) -> list[JobRead]:
    return await service.list_jobs(target_server_id=target_server_id)


@router.get("/actions", response_model=list[OperationalActionRead])
async def list_actions(
    service: Annotated[JobService, Depends(get_job_service)],
) -> list[OperationalActionRead]:
    return await service.list_actions()


@router.post("/actions/execute", response_model=JobRead, status_code=status.HTTP_201_CREATED)
async def execute_action(
    payload: JobActionExecuteRequest,
    service: Annotated[JobService, Depends(get_job_service)],
) -> JobRead:
    try:
        return await service.execute_action(payload)
    except JobTargetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobTargetNotManagedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except OperationalActionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/actions", response_model=OperationalActionRead, status_code=status.HTTP_201_CREATED)
async def create_action(
    payload: OperationalActionCreate,
    service: Annotated[JobService, Depends(get_job_service)],
) -> OperationalActionRead:
    try:
        return await service.create_action(payload)
    except OperationalActionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.put("/actions/{action_id}", response_model=OperationalActionRead)
async def update_action(
    action_id: str,
    payload: OperationalActionUpdate,
    service: Annotated[JobService, Depends(get_job_service)],
) -> OperationalActionRead:
    try:
        return await service.update_action(action_id, payload)
    except BuiltinOperationalActionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except OperationalActionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/actions/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_action(
    action_id: str,
    service: Annotated[JobService, Depends(get_job_service)],
) -> None:
    try:
        await service.delete_action(action_id)
    except BuiltinOperationalActionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except OperationalActionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/execute/bulk", response_model=BulkExecutionRead, status_code=status.HTTP_201_CREATED)
async def execute_job_bulk(
    payload: JobBulkExecuteRequest,
    service: Annotated[JobService, Depends(get_job_service)],
) -> BulkExecutionRead:
    return await service.execute_bulk(payload)


@router.get("/{job_id}", response_model=JobRead)
async def get_job(
    job_id: UUID,
    service: Annotated[JobService, Depends(get_job_service)],
) -> JobRead:
    try:
        return await service.get_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/execute", response_model=JobRead, status_code=status.HTTP_201_CREATED)
async def execute_job(
    payload: JobExecuteRequest,
    service: Annotated[JobService, Depends(get_job_service)],
) -> JobRead:
    try:
        return await service.execute(payload)
    except JobTargetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobTargetNotManagedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{job_id}/cancel", response_model=JobRead)
async def cancel_job(
    job_id: UUID,
    service: Annotated[JobService, Depends(get_job_service)],
) -> JobRead:
    try:
        return await service.cancel_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

````

