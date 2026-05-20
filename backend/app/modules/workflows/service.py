from datetime import UTC, datetime
from uuid import UUID

from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.workflows.models import (
    WorkflowRun,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepStatus,
)
from backend.app.modules.workflows.repository import WorkflowRunRepository, WorkflowStepRepository
from backend.app.modules.workflows.schemas import WorkflowCreate, WorkflowRunRead, WorkflowStepCreate, WorkflowStepRead


class WorkflowNotFoundError(Exception):
    """Raised when a workflow run cannot be found."""


class WorkflowStepNotFoundError(Exception):
    """Raised when a workflow step cannot be found."""


class WorkflowInvalidTransitionError(Exception):
    """Raised when a workflow transition is not valid."""


class WorkflowService:
    def __init__(
        self,
        *,
        workflow_repository: WorkflowRunRepository,
        step_repository: WorkflowStepRepository,
        server_repository: ServerRepository | None = None,
    ) -> None:
        self.workflow_repository = workflow_repository
        self.step_repository = step_repository
        self.server_repository = server_repository

    async def list_workflows(self) -> list[WorkflowRunRead]:
        return [await self._to_read(item) for item in await self.workflow_repository.list()]

    async def get_workflow(self, workflow_run_id: UUID) -> WorkflowRunRead:
        workflow = await self.workflow_repository.get_by_id(workflow_run_id)
        if workflow is None:
            raise WorkflowNotFoundError("Workflow run not found")
        return await self._to_read(workflow)

    async def create_workflow(self, payload: WorkflowCreate) -> WorkflowRunRead:
        workflow = await self.workflow_repository.create(
            WorkflowRun(
                workflow_type=payload.workflow_type,
                trigger_source=payload.trigger_source,
                target_server_id=payload.target_server_id,
                initiated_by=payload.initiated_by,
                context_json=payload.context_json,
                status=WorkflowStatus.PENDING,
            )
        )
        await self.workflow_repository.session.commit()
        return await self._to_read(workflow)

    async def mark_queued(self, workflow_run_id: UUID) -> WorkflowRunRead:
        workflow = await self._workflow(workflow_run_id)
        workflow.status = WorkflowStatus.QUEUED
        await self.workflow_repository.session.commit()
        await self.workflow_repository.session.refresh(workflow, attribute_names=["steps"])
        return await self._to_read(workflow)

    async def start_workflow(self, workflow_run_id: UUID) -> WorkflowRunRead:
        workflow = await self._workflow(workflow_run_id)
        if workflow.status == WorkflowStatus.CANCELLED:
            raise WorkflowInvalidTransitionError("Cancelled workflow cannot be started")
        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = workflow.started_at or datetime.now(UTC)
        await self.workflow_repository.session.commit()
        await self.workflow_repository.session.refresh(workflow, attribute_names=["steps"])
        return await self._to_read(workflow)

    async def complete_workflow(self, workflow_run_id: UUID, result_summary: dict | None = None) -> WorkflowRunRead:
        workflow = await self._workflow(workflow_run_id)
        workflow.status = WorkflowStatus.SUCCESS
        workflow.finished_at = datetime.now(UTC)
        workflow.result_summary = result_summary or workflow.result_summary
        await self.workflow_repository.session.commit()
        await self.workflow_repository.session.refresh(workflow, attribute_names=["steps"])
        return await self._to_read(workflow)

    async def fail_workflow(self, workflow_run_id: UUID, error_message: str, result_summary: dict | None = None) -> WorkflowRunRead:
        workflow = await self._workflow(workflow_run_id)
        workflow.status = WorkflowStatus.FAILED
        workflow.finished_at = datetime.now(UTC)
        workflow.error_message = error_message
        workflow.result_summary = result_summary or workflow.result_summary
        await self.workflow_repository.session.commit()
        await self.workflow_repository.session.refresh(workflow, attribute_names=["steps"])
        return await self._to_read(workflow)

    async def cancel_workflow(self, workflow_run_id: UUID) -> WorkflowRunRead:
        workflow = await self._workflow(workflow_run_id)
        workflow.status = WorkflowStatus.CANCELLED
        workflow.finished_at = datetime.now(UTC)
        await self.workflow_repository.session.commit()
        await self.workflow_repository.session.refresh(workflow, attribute_names=["steps"])
        return await self._to_read(workflow)

    async def add_step(self, workflow_run_id: UUID, payload: WorkflowStepCreate) -> WorkflowStepRead:
        await self._workflow(workflow_run_id)
        step = await self.step_repository.create(
            WorkflowStep(
                workflow_run_id=workflow_run_id,
                step_order=payload.step_order,
                step_type=payload.step_type,
                name=payload.name,
                metadata_json=payload.metadata_json,
            )
        )
        await self.step_repository.session.commit()
        return await self._step_to_read(step)

    async def start_step(self, step_id: UUID) -> WorkflowStepRead:
        step = await self._step(step_id)
        step.status = WorkflowStepStatus.RUNNING
        step.started_at = step.started_at or datetime.now(UTC)
        await self.step_repository.session.commit()
        await self.step_repository.session.refresh(step)
        return await self._step_to_read(step)

    async def complete_step(self, step_id: UUID, log_output: str | None = None, metadata_json: dict | None = None) -> WorkflowStepRead:
        step = await self._step(step_id)
        step.status = WorkflowStepStatus.SUCCESS
        step.finished_at = datetime.now(UTC)
        if log_output:
            step.log_output = self._append_text(step.log_output, log_output)
        if metadata_json:
            step.metadata_json = {**step.metadata_json, **metadata_json}
        await self.step_repository.session.commit()
        await self.step_repository.session.refresh(step)
        return await self._step_to_read(step)

    async def fail_step(self, step_id: UUID, error_output: str, log_output: str | None = None) -> WorkflowStepRead:
        step = await self._step(step_id)
        step.status = WorkflowStepStatus.FAILED
        step.finished_at = datetime.now(UTC)
        step.error_output = self._append_text(step.error_output, error_output)
        if log_output:
            step.log_output = self._append_text(step.log_output, log_output)
        await self.step_repository.session.commit()
        await self.step_repository.session.refresh(step)
        return await self._step_to_read(step)

    async def append_log(self, step_id: UUID, message: str, *, stderr: bool = False) -> WorkflowStepRead:
        step = await self._step(step_id)
        if stderr:
            step.error_output = self._append_text(step.error_output, message)
        else:
            step.log_output = self._append_text(step.log_output, message)
        await self.step_repository.session.commit()
        await self.step_repository.session.refresh(step)
        return await self._step_to_read(step)

    async def _workflow(self, workflow_run_id: UUID) -> WorkflowRun:
        workflow = await self.workflow_repository.get_by_id(workflow_run_id)
        if workflow is None:
            raise WorkflowNotFoundError("Workflow run not found")
        return workflow

    async def _step(self, step_id: UUID) -> WorkflowStep:
        step = await self.step_repository.get_by_id(step_id)
        if step is None:
            raise WorkflowStepNotFoundError("Workflow step not found")
        return step

    @staticmethod
    def _append_text(existing: str, message: str) -> str:
        if not existing:
            return message
        return f"{existing.rstrip()}\n{message}"

    async def _to_read(self, workflow: WorkflowRun) -> WorkflowRunRead:
        data = WorkflowRunRead.model_validate(workflow)
        hostname = await self._hostname(workflow.target_server_id)
        steps = [await self._step_to_read(step) for step in workflow.steps]
        target_nodes = [item for item in {hostname, *[step.target_hostname for step in steps]} if item]
        linked_job_ids: list[str] = []
        for step in steps:
            raw_job_ids = step.metadata_json.get("job_ids") if step.metadata_json else None
            if isinstance(raw_job_ids, list):
                linked_job_ids.extend(str(job_id) for job_id in raw_job_ids)
        current_step = next((step.name for step in steps if step.status == WorkflowStepStatus.RUNNING), None)
        return data.model_copy(
            update={
                "target_hostname": hostname,
                "steps": steps,
                "current_step": current_step,
                "completed_steps": sum(1 for step in steps if step.status == WorkflowStepStatus.SUCCESS),
                "failed_steps": sum(1 for step in steps if step.status == WorkflowStepStatus.FAILED),
                "duration_seconds": self._duration_seconds(workflow.started_at, workflow.finished_at),
                "target_nodes": target_nodes,
                "linked_job_ids": sorted(set(linked_job_ids)),
            }
        )

    async def _step_to_read(self, step: WorkflowStep) -> WorkflowStepRead:
        data = WorkflowStepRead.model_validate(step)
        target_server_id = step.metadata_json.get("target_server_id") if step.metadata_json else None
        hostname = await self._hostname(target_server_id)
        return data.model_copy(update={"target_hostname": hostname})

    async def _hostname(self, server_id) -> str | None:
        if self.server_repository is None or not server_id:
            return None
        try:
            server_uuid = server_id if isinstance(server_id, UUID) else UUID(str(server_id))
        except ValueError:
            return None
        server = await self.server_repository.get_by_id(server_uuid)
        return server.hostname if server else None

    @staticmethod
    def _duration_seconds(started_at: datetime | None, finished_at: datetime | None) -> int | None:
        if started_at is None:
            return None
        start = started_at if started_at.tzinfo else started_at.replace(tzinfo=UTC)
        end = finished_at or datetime.now(UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        return max(0, int((end - start).total_seconds()))
