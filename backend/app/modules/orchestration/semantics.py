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
