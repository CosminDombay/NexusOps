from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

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
