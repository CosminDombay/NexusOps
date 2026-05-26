from datetime import UTC, datetime, timedelta
from enum import StrEnum
from types import SimpleNamespace
from uuid import uuid4

from backend.app.modules.orchestration.utils import (
    aggregate_target_executions,
    duration_seconds,
    rollup_status,
    success_failure_counts,
    summarize_statuses,
)
from backend.app.common.variables import VariableResolutionService
from backend.app.modules.deployments.models import DeploymentStatus
from backend.app.modules.deployments.runtime import (
    DeploymentRuntimeInspector,
    expected_compose_services,
)
from backend.app.modules.jobs.models import JobStatus
from backend.app.modules.orchestration.security import (
    CommandValidationError,
    SafeCommandBuilder,
    SecretSanitizer,
    redact_sensitive_text,
)
from backend.app.modules.orchestration.semantics import (
    is_job_failure,
    is_job_success,
    orchestration_origin,
    runtime_metadata,
)
from backend.app.modules.orchestration.transitions import (
    InvalidDeploymentStateTransitionError,
    InvalidWorkflowStateTransitionError,
    validate_deployment_transition,
    validate_workflow_transition,
)
from backend.app.modules.workflows.models import WorkflowStatus


class DemoStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    RUNNING = "running"
    DEGRADED = "degraded"


def test_duration_seconds_handles_naive_and_aware_dates() -> None:
    started_at = datetime(2026, 5, 24, 10, 0, 0)
    finished_at = datetime(2026, 5, 24, 10, 0, 7, tzinfo=UTC)

    assert duration_seconds(started_at, finished_at) == 7


def test_duration_seconds_can_require_finished_time() -> None:
    started_at = datetime.now(UTC) - timedelta(seconds=5)

    assert duration_seconds(started_at, None, default_to_now=False) is None
    assert duration_seconds(started_at, None) >= 5


def test_summarize_statuses_counts_success_and_failure_states() -> None:
    summary = summarize_statuses(
        [
            SimpleNamespace(status=DemoStatus.SUCCESS),
            SimpleNamespace(status=DemoStatus.RUNNING),
            SimpleNamespace(status=DemoStatus.FAILED),
        ],
        success_states={DemoStatus.SUCCESS, DemoStatus.RUNNING},
        failure_states={DemoStatus.FAILED},
    )

    assert summary.total_count == 3
    assert summary.success_count == 2
    assert summary.failed_count == 1
    assert summary.has_failures


def test_rollup_status_preserves_partial_success_semantics() -> None:
    result = rollup_status(
        [DemoStatus.SUCCESS, DemoStatus.FAILED],
        success_states={DemoStatus.SUCCESS},
        failure_states={DemoStatus.FAILED},
        empty_status=DemoStatus.FAILED,
        all_success_status=DemoStatus.SUCCESS,
        partial_success_status=DemoStatus.RUNNING,
        all_failed_status=DemoStatus.FAILED,
        mixed_status=DemoStatus.DEGRADED,
    )

    assert result == DemoStatus.RUNNING


def test_aggregate_target_executions_collects_counts_jobs_and_errors() -> None:
    job_id = uuid4()
    aggregate = aggregate_target_executions(
        [
            SimpleNamespace(status=DemoStatus.SUCCESS, job_id=job_id, error_message=None),
            SimpleNamespace(status=DemoStatus.FAILED, job_id=None, error_message="boom"),
        ],
        success_states={DemoStatus.SUCCESS},
        failure_states={DemoStatus.FAILED},
    )

    assert aggregate.summary.as_result_summary() == {
        "target_count": 2,
        "success_count": 1,
        "failed_count": 1,
        "job_ids": [str(job_id)],
    }
    assert aggregate.summary.failure_messages == ["boom"]
    assert aggregate.statuses == [DemoStatus.SUCCESS, DemoStatus.FAILED]


def test_success_failure_counts_uses_shared_bulk_counting() -> None:
    success_count, failure_count = success_failure_counts(
        [SimpleNamespace(success=True), SimpleNamespace(success=False)]
    )

    assert success_count == 1
    assert failure_count == 1


def test_job_lifecycle_semantics_treat_completed_as_success() -> None:
    assert is_job_success(JobStatus.SUCCESS)
    assert is_job_success(JobStatus.COMPLETED)
    assert is_job_failure(JobStatus.FAILED)
    assert is_job_failure(JobStatus.CANCELLED)
    assert is_job_failure(JobStatus.STALE)


def test_runtime_metadata_uses_consistent_keys() -> None:
    metadata = runtime_metadata(
        operation_type="profile:base-linux-server:install-docker",
        correlation_id="corr-1",
        target_hostname="node-01",
        target_server_id="server-1",
        transport="fake-ssh",
    )

    assert metadata == {
        "execution_origin": "profile",
        "operation_type": "profile:base-linux-server:install-docker",
        "correlation_id": "corr-1",
        "target_hostname": "node-01",
        "target_server_id": "server-1",
        "transport": "fake-ssh",
    }
    assert orchestration_origin("package:docker-engine") == "package"


def test_command_builder_rejects_injected_interpolated_values() -> None:
    builder = SafeCommandBuilder(VariableResolutionService())

    try:
        builder.resolve_template(
            "echo {{ value }}",
            definitions=[{"name": "value", "required": True}],
            variables={"value": "ok; rm -rf /"},
            source="test",
        )
    except CommandValidationError as exc:
        assert "Unsafe shell control token" in str(exc)
    else:
        raise AssertionError("expected command validation failure")


def test_command_builder_escapes_safe_interpolated_values() -> None:
    builder = SafeCommandBuilder(VariableResolutionService())

    command = builder.resolve_template(
        "echo {{ value }}",
        definitions=[{"name": "value", "required": True}],
        variables={"value": "hello world"},
        source="test",
    )

    assert command == "echo 'hello world'"


def test_secret_sanitizer_redacts_common_secret_shapes() -> None:
    sanitizer = SecretSanitizer(["super-secret"])

    assert sanitizer.redact_text("token=abc123 and value=super-secret") == "token=******** and value=********"
    assert redact_sensitive_text("Bearer abc.def.ghi") == "********"


def test_workflow_transition_validator_rejects_terminal_restart() -> None:
    try:
        validate_workflow_transition(WorkflowStatus.SUCCESS, WorkflowStatus.RUNNING)
    except InvalidWorkflowStateTransitionError:
        pass
    else:
        raise AssertionError("expected invalid workflow transition")


def test_deployment_transition_validator_rejects_cancelled_to_success() -> None:
    try:
        validate_deployment_transition(DeploymentStatus.CANCELLED, DeploymentStatus.SUCCESS)
    except InvalidDeploymentStateTransitionError:
        pass
    else:
        raise AssertionError("expected invalid deployment transition")


def test_expected_compose_services_reads_service_names() -> None:
    compose = """
services:
  web:
    image: nginx
  worker:
    image: busybox
volumes:
  data:
"""

    assert expected_compose_services(compose) == {"web", "worker"}


def test_runtime_inspector_marks_stopped_container_as_drifted() -> None:
    state = DeploymentRuntimeInspector.parse(
        target_server_id=uuid4(),
        stdout='{"Name":"demo-web-1","State":"exited","Config":{"Labels":{}},"Labels":{"com.docker.compose.service":"web"}}\n',
        expected_services={"web"},
        desired_running=True,
    )

    assert state.status == DeploymentStatus.STOPPED
    assert state.runtime_state == "stopped"
    assert state.sync_status == "drifted"
    assert state.health_state == "unhealthy"


def test_runtime_inspector_marks_partial_stack_as_degraded() -> None:
    state = DeploymentRuntimeInspector.parse(
        target_server_id=uuid4(),
        stdout=(
            '{"Name":"demo-web-1","State":"running","Labels":{"com.docker.compose.service":"web"}}\n'
            '{"Name":"demo-worker-1","State":"exited","Labels":{"com.docker.compose.service":"worker"}}\n'
        ),
        expected_services={"web", "worker"},
        desired_running=True,
    )

    assert state.status == DeploymentStatus.DEGRADED
    assert state.runtime_state == "degraded"
    assert state.sync_status == "drifted"
