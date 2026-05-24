from __future__ import annotations

from backend.app.modules.deployments.models import DeploymentStatus
from backend.app.modules.workflows.models import WorkflowStatus, WorkflowStepStatus


class InvalidWorkflowStateTransitionError(Exception):
    """Raised when a workflow run transition violates the lifecycle state machine."""


class InvalidWorkflowStepStateTransitionError(Exception):
    """Raised when a workflow step transition violates the lifecycle state machine."""


class InvalidDeploymentStateTransitionError(Exception):
    """Raised when a deployment transition violates the lifecycle state machine."""


VALID_WORKFLOW_TRANSITIONS: dict[WorkflowStatus, set[WorkflowStatus]] = {
    WorkflowStatus.PENDING: {WorkflowStatus.QUEUED, WorkflowStatus.RUNNING, WorkflowStatus.CANCELLED, WorkflowStatus.FAILED},
    WorkflowStatus.QUEUED: {WorkflowStatus.RUNNING, WorkflowStatus.CANCELLED, WorkflowStatus.FAILED},
    WorkflowStatus.RUNNING: {WorkflowStatus.SUCCESS, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED},
    WorkflowStatus.SUCCESS: set(),
    WorkflowStatus.FAILED: set(),
    WorkflowStatus.CANCELLED: set(),
}

VALID_WORKFLOW_STEP_TRANSITIONS: dict[WorkflowStepStatus, set[WorkflowStepStatus]] = {
    WorkflowStepStatus.PENDING: {WorkflowStepStatus.RUNNING, WorkflowStepStatus.SUCCESS, WorkflowStepStatus.FAILED, WorkflowStepStatus.SKIPPED},
    WorkflowStepStatus.RUNNING: {WorkflowStepStatus.SUCCESS, WorkflowStepStatus.FAILED, WorkflowStepStatus.SKIPPED},
    WorkflowStepStatus.SUCCESS: set(),
    WorkflowStepStatus.FAILED: set(),
    WorkflowStepStatus.SKIPPED: set(),
}

VALID_DEPLOYMENT_TRANSITIONS: dict[DeploymentStatus, set[DeploymentStatus]] = {
    DeploymentStatus.DRAFT: {DeploymentStatus.QUEUED, DeploymentStatus.DEPLOYING, DeploymentStatus.CANCELLED, DeploymentStatus.FAILED},
    DeploymentStatus.QUEUED: {DeploymentStatus.DEPLOYING, DeploymentStatus.CANCELLED, DeploymentStatus.FAILED},
    DeploymentStatus.DEPLOYING: {
        DeploymentStatus.RUNNING,
        DeploymentStatus.SUCCESS,
        DeploymentStatus.PARTIAL_SUCCESS,
        DeploymentStatus.DEGRADED,
        DeploymentStatus.STOPPED,
        DeploymentStatus.FAILED,
        DeploymentStatus.CANCELLED,
    },
    DeploymentStatus.RUNNING: {DeploymentStatus.QUEUED, DeploymentStatus.DEPLOYING, DeploymentStatus.STOPPED, DeploymentStatus.DEGRADED, DeploymentStatus.FAILED, DeploymentStatus.CANCELLED},
    DeploymentStatus.SUCCESS: {DeploymentStatus.QUEUED, DeploymentStatus.DEPLOYING, DeploymentStatus.STOPPED, DeploymentStatus.DEGRADED, DeploymentStatus.FAILED, DeploymentStatus.CANCELLED},
    DeploymentStatus.PARTIAL_SUCCESS: {DeploymentStatus.QUEUED, DeploymentStatus.DEPLOYING, DeploymentStatus.RUNNING, DeploymentStatus.STOPPED, DeploymentStatus.DEGRADED, DeploymentStatus.FAILED, DeploymentStatus.CANCELLED},
    DeploymentStatus.DEGRADED: {DeploymentStatus.QUEUED, DeploymentStatus.DEPLOYING, DeploymentStatus.RUNNING, DeploymentStatus.STOPPED, DeploymentStatus.FAILED, DeploymentStatus.CANCELLED},
    DeploymentStatus.STOPPED: {DeploymentStatus.QUEUED, DeploymentStatus.DEPLOYING, DeploymentStatus.RUNNING, DeploymentStatus.FAILED, DeploymentStatus.CANCELLED},
    DeploymentStatus.FAILED: {DeploymentStatus.QUEUED, DeploymentStatus.DEPLOYING},
    DeploymentStatus.CANCELLED: set(),
}


def validate_workflow_transition(current: WorkflowStatus, next_status: WorkflowStatus) -> None:
    if current == next_status:
        return
    if next_status not in VALID_WORKFLOW_TRANSITIONS[current]:
        raise InvalidWorkflowStateTransitionError(
            f"Cannot transition workflow from {current.value} to {next_status.value}"
        )


def validate_workflow_step_transition(current: WorkflowStepStatus, next_status: WorkflowStepStatus) -> None:
    if current == next_status:
        return
    if next_status not in VALID_WORKFLOW_STEP_TRANSITIONS[current]:
        raise InvalidWorkflowStepStateTransitionError(
            f"Cannot transition workflow step from {current.value} to {next_status.value}"
        )


def validate_deployment_transition(current: DeploymentStatus, next_status: DeploymentStatus) -> None:
    if current == next_status:
        return
    if next_status not in VALID_DEPLOYMENT_TRANSITIONS[current]:
        raise InvalidDeploymentStateTransitionError(
            f"Cannot transition deployment from {current.value} to {next_status.value}"
        )
