from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
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

    async def list_for_target(self, target_server_id: UUID) -> list[WorkflowRun]:
        result = await self.session.execute(
            select(WorkflowRun)
            .outerjoin(WorkflowStep, WorkflowStep.workflow_run_id == WorkflowRun.id)
            .options(selectinload(WorkflowRun.steps))
            .where(
                or_(
                    WorkflowRun.target_server_id == target_server_id,
                    WorkflowStep.metadata_json["target_server_id"].as_string() == str(target_server_id),
                )
            )
            .order_by(WorkflowRun.created_at.desc())
        )
        return list(result.scalars().unique().all())


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
