"""Startup reconciliation for work that was in flight when the process stopped.

Jobs and workflow runs execute on the in-process async queue, which has no
durable state. A restart therefore abandons anything mid-flight while its
database row still claims to be queued, dispatched, or running. Those rows never
move again, so the UI shows a job running forever and stale-state checks never
fire.

Reconciliation runs once at startup and closes out every orphaned record.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import select, update

from backend.app.db.session import AsyncSessionLocal
from backend.app.modules.jobs.models import Job, JobStatus
from backend.app.modules.workflows.models import (
    WorkflowRun,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepStatus,
)

logger = structlog.get_logger(__name__)

STALE_MESSAGE = "Interrupted by a NexusOps restart; the remote outcome is unknown."

# Statuses that only ever hold while an in-process task owns the record.
ORPHANED_JOB_STATUSES = (
    JobStatus.PENDING,
    JobStatus.QUEUED,
    JobStatus.DISPATCHED,
    JobStatus.RUNNING,
)
ORPHANED_WORKFLOW_STATUSES = (
    WorkflowStatus.PENDING,
    WorkflowStatus.QUEUED,
    WorkflowStatus.RUNNING,
)
ORPHANED_STEP_STATUSES = (
    WorkflowStepStatus.PENDING,
    WorkflowStepStatus.RUNNING,
)


async def reconcile_interrupted_executions() -> dict[str, int]:
    """Mark orphaned jobs and workflow runs as stale. Returns per-entity counts."""
    now = datetime.now(UTC)
    counts = {"jobs": 0, "workflow_runs": 0, "workflow_steps": 0}

    async with AsyncSessionLocal() as session:
        jobs = (
            await session.execute(select(Job).where(Job.status.in_(ORPHANED_JOB_STATUSES)))
        ).scalars().all()
        for job in jobs:
            job.status = JobStatus.STALE
            job.completed_at = job.completed_at or now
            job.stderr = f"{job.stderr}\n{STALE_MESSAGE}" if job.stderr else STALE_MESSAGE
        counts["jobs"] = len(jobs)

        runs = (
            await session.execute(
                select(WorkflowRun).where(WorkflowRun.status.in_(ORPHANED_WORKFLOW_STATUSES))
            )
        ).scalars().all()
        for run in runs:
            run.status = WorkflowStatus.FAILED
            run.finished_at = run.finished_at or now
            run.error_message = run.error_message or STALE_MESSAGE
        counts["workflow_runs"] = len(runs)

        if runs:
            step_result = await session.execute(
                update(WorkflowStep)
                .where(
                    WorkflowStep.workflow_run_id.in_([run.id for run in runs]),
                    WorkflowStep.status.in_(ORPHANED_STEP_STATUSES),
                )
                .values(status=WorkflowStepStatus.FAILED, finished_at=now)
            )
            counts["workflow_steps"] = step_result.rowcount or 0

        await session.commit()

    if any(counts.values()):
        logger.warning("startup.reconciled_interrupted_executions", **counts)
    else:
        logger.info("startup.no_interrupted_executions")
    return counts
