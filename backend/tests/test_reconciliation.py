"""Startup reconciliation of executions interrupted by a restart.

The task queue is in-process and non-durable, so a restart abandons anything
mid-flight. Without reconciliation those rows stayed 'running' forever.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.db.base import Base
from backend.app.modules.jobs.models import Job, JobStatus
from backend.app.modules.orchestration import reconciliation
from backend.app.modules.workflows.models import (
    WorkflowRun,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepStatus,
    WorkflowType,
)


@pytest.fixture()
async def session_factory(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'reconcile.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(reconciliation, "AsyncSessionLocal", factory)
    yield factory
    await engine.dispose()


def _job(status: JobStatus, **overrides) -> Job:
    fields = {
        "target_server_id": uuid4(),
        "operation_type": "command",
        "command": "echo hi",
        "status": status,
    }
    fields.update(overrides)
    return Job(**fields)


async def _add(factory: async_sessionmaker, *records) -> None:
    async with factory() as session:
        session.add_all(records)
        await session.commit()


async def _statuses(factory: async_sessionmaker, model) -> list:
    async with factory() as session:
        from sqlalchemy import select

        return [row.status for row in (await session.execute(select(model))).scalars().all()]


@pytest.mark.parametrize(
    "status",
    [JobStatus.PENDING, JobStatus.QUEUED, JobStatus.DISPATCHED, JobStatus.RUNNING],
)
async def test_in_flight_jobs_become_stale(session_factory, status: JobStatus) -> None:
    await _add(session_factory, _job(status))

    counts = await reconciliation.reconcile_interrupted_executions()

    assert counts["jobs"] == 1
    assert await _statuses(session_factory, Job) == [JobStatus.STALE]


@pytest.mark.parametrize(
    "status",
    [JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.STALE, JobStatus.COMPLETED],
)
async def test_settled_jobs_are_left_alone(session_factory, status: JobStatus) -> None:
    await _add(session_factory, _job(status))

    counts = await reconciliation.reconcile_interrupted_executions()

    assert counts["jobs"] == 0
    assert await _statuses(session_factory, Job) == [status]


async def test_stale_job_records_a_reason(session_factory) -> None:
    await _add(session_factory, _job(JobStatus.RUNNING))

    await reconciliation.reconcile_interrupted_executions()

    async with session_factory() as session:
        from sqlalchemy import select

        job = (await session.execute(select(Job))).scalars().one()
    assert reconciliation.STALE_MESSAGE in (job.stderr or "")
    assert job.completed_at is not None


async def test_existing_completed_at_is_preserved(session_factory) -> None:
    finished = datetime(2026, 1, 1, tzinfo=UTC)
    await _add(session_factory, _job(JobStatus.RUNNING, completed_at=finished))

    await reconciliation.reconcile_interrupted_executions()

    async with session_factory() as session:
        from sqlalchemy import select

        job = (await session.execute(select(Job))).scalars().one()
    assert job.completed_at.replace(tzinfo=UTC) == finished


async def test_in_flight_workflow_runs_and_steps_fail(session_factory) -> None:
    run = WorkflowRun(workflow_type=WorkflowType.PACKAGE_EXECUTION, status=WorkflowStatus.RUNNING)
    await _add(session_factory, run)
    await _add(
        session_factory,
        WorkflowStep(
            workflow_run_id=run.id,
            name="step-1",
            step_order=0,
            step_type="command",
            status=WorkflowStepStatus.RUNNING,
        ),
        WorkflowStep(
            workflow_run_id=run.id,
            name="step-2",
            step_order=1,
            step_type="command",
            status=WorkflowStepStatus.SUCCESS,
        ),
    )

    counts = await reconciliation.reconcile_interrupted_executions()

    assert counts["workflow_runs"] == 1
    assert counts["workflow_steps"] == 1
    assert await _statuses(session_factory, WorkflowRun) == [WorkflowStatus.FAILED]
    assert sorted(await _statuses(session_factory, WorkflowStep)) == sorted(
        [WorkflowStepStatus.FAILED, WorkflowStepStatus.SUCCESS]
    )


async def test_reconciliation_is_idempotent(session_factory) -> None:
    await _add(session_factory, _job(JobStatus.RUNNING))

    first = await reconciliation.reconcile_interrupted_executions()
    second = await reconciliation.reconcile_interrupted_executions()

    assert first["jobs"] == 1
    assert second["jobs"] == 0


async def test_clean_start_reports_nothing(session_factory) -> None:
    counts = await reconciliation.reconcile_interrupted_executions()
    assert counts == {"jobs": 0, "workflow_runs": 0, "workflow_steps": 0}
