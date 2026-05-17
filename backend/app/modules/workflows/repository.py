from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.common.repository import BaseRepository
from backend.app.modules.workflows.models import WorkflowRun, WorkflowStep


class WorkflowRunRepository(BaseRepository[WorkflowRun]):
    async def create(self, workflow_run: WorkflowRun) -> WorkflowRun:
        self.session.add(workflow_run)
        await self.session.flush()
        await self.session.refresh(workflow_run, attribute_names=["steps"])
        return workflow_run

    async def get_by_id(self, workflow_run_id: UUID) -> WorkflowRun | None:
        result = await self.session.execute(
            select(WorkflowRun)
            .options(selectinload(WorkflowRun.steps))
            .where(WorkflowRun.id == workflow_run_id)
        )
        return result.scalar_one_or_none()

    async def list(self) -> list[WorkflowRun]:
        result = await self.session.execute(
            select(WorkflowRun)
            .options(selectinload(WorkflowRun.steps))
            .order_by(WorkflowRun.created_at.desc())
        )
        return list(result.scalars().all())


class WorkflowStepRepository(BaseRepository[WorkflowStep]):
    async def create(self, step: WorkflowStep) -> WorkflowStep:
        self.session.add(step)
        await self.session.flush()
        await self.session.refresh(step)
        return step

    async def get_by_id(self, step_id: UUID) -> WorkflowStep | None:
        result = await self.session.execute(select(WorkflowStep).where(WorkflowStep.id == step_id))
        return result.scalar_one_or_none()

    async def list_for_workflow(self, workflow_run_id: UUID) -> list[WorkflowStep]:
        result = await self.session.execute(
            select(WorkflowStep)
            .where(WorkflowStep.workflow_run_id == workflow_run_id)
            .order_by(WorkflowStep.step_order.asc())
        )
        return list(result.scalars().all())
