from datetime import UTC, datetime
from uuid import UUID

from backend.app.modules.audit.repository import AuditEventRepository
from backend.app.modules.audit.service import AuditService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.orchestration.activity import workflow_activity_timeline
from backend.app.modules.orchestration.security import SecretSanitizer
from backend.app.modules.orchestration.transitions import (
    validate_workflow_step_transition,
    validate_workflow_transition,
)
from backend.app.modules.orchestration.utils import duration_seconds, summarize_statuses
from backend.app.modules.workflows.models import (
    WorkflowRun,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepStatus,
)
from backend.app.modules.workflows.repository import WorkflowRunRepository, WorkflowStepRepository
from backend.app.modules.workflows.schemas import (
    WorkflowCreate,
    WorkflowRunRead,
    WorkflowStepCreate,
    WorkflowStepRead,
)


class WorkflowNotFoundError(Exception):
    """Raised when a workflow run cannot be found."""


class WorkflowStepNotFoundError(Exception):
    """Raised when a workflow step cannot be found."""


class WorkflowInvalidTransitionError(Exception):
    """Raised when a workflow transition is not valid."""


class WorkflowTransitionManager:
    """Owns workflow lifecycle timestamps and transition validation."""

    @staticmethod
    def transition_run(workflow: WorkflowRun, next_status: WorkflowStatus) -> None:
        validate_workflow_transition(workflow.status, next_status)
        now = datetime.now(UTC)
        workflow.status = next_status
        if next_status == WorkflowStatus.RUNNING:
            workflow.started_at = workflow.started_at or now
        if next_status in {WorkflowStatus.SUCCESS, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED}:
            workflow.finished_at = workflow.finished_at or now

    @staticmethod
    def transition_step(step: WorkflowStep, next_status: WorkflowStepStatus) -> None:
        validate_workflow_step_transition(step.status, next_status)
        now = datetime.now(UTC)
        step.status = next_status
        if next_status == WorkflowStepStatus.RUNNING:
            step.started_at = step.started_at or now
        if next_status in {WorkflowStepStatus.SUCCESS, WorkflowStepStatus.FAILED, WorkflowStepStatus.SKIPPED}:
            step.finished_at = step.finished_at or now


class WorkflowSummaryBuilder:
    """Builds derived workflow read-model fields from steps and metadata."""

    @staticmethod
    def step_summary(steps: list[WorkflowStepRead]):
        return summarize_statuses(
            steps,
            success_states={WorkflowStepStatus.SUCCESS},
            failure_states={WorkflowStepStatus.FAILED},
        )

    @staticmethod
    def linked_job_ids(steps: list[WorkflowStepRead]) -> list[str]:
        linked_job_ids: list[str] = []
        for step in steps:
            raw_job_ids = step.metadata_json.get("job_ids") if step.metadata_json else None
            if isinstance(raw_job_ids, list):
                linked_job_ids.extend(str(job_id) for job_id in raw_job_ids)
        return sorted(set(linked_job_ids))


class WorkflowService:
    def __init__(
        self,
        *,
        workflow_repository: WorkflowRunRepository,
        step_repository: WorkflowStepRepository,
        server_repository: ServerRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        self.workflow_repository = workflow_repository
        self.step_repository = step_repository
        self.server_repository = server_repository
        self.audit_service = audit_service or AuditService(AuditEventRepository(workflow_repository.session))
        self.transition_manager = WorkflowTransitionManager()
        self.summary_builder = WorkflowSummaryBuilder()
        self.secret_sanitizer = SecretSanitizer()

    async def list_workflows(self, *, target_server_id: UUID | None = None) -> list[WorkflowRunRead]:
        workflows = (
            await self.workflow_repository.list_for_target(target_server_id)
            if target_server_id is not None
            else await self.workflow_repository.list()
        )
        return [await self._to_read(item) for item in workflows]

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
        await self._audit_workflow(workflow, "workflow.created", "success")
        return await self._to_read(workflow)

    async def mark_queued(self, workflow_run_id: UUID) -> WorkflowRunRead:
        workflow = await self._workflow(workflow_run_id)
        self.transition_manager.transition_run(workflow, WorkflowStatus.QUEUED)
        await self.workflow_repository.session.commit()
        await self.workflow_repository.session.refresh(workflow, attribute_names=["steps"])
        await self._audit_workflow(workflow, "workflow.queued", "success")
        return await self._to_read(workflow)

    async def start_workflow(self, workflow_run_id: UUID) -> WorkflowRunRead:
        workflow = await self._workflow(workflow_run_id)
        self.transition_manager.transition_run(workflow, WorkflowStatus.RUNNING)
        await self.workflow_repository.session.commit()
        await self.workflow_repository.session.refresh(workflow, attribute_names=["steps"])
        await self._audit_workflow(workflow, "workflow.started", "success")
        return await self._to_read(workflow)

    async def complete_workflow(self, workflow_run_id: UUID, result_summary: dict | None = None) -> WorkflowRunRead:
        workflow = await self._workflow(workflow_run_id)
        self.transition_manager.transition_run(workflow, WorkflowStatus.SUCCESS)
        workflow.result_summary = self.secret_sanitizer.redact_value(result_summary or workflow.result_summary)
        await self.workflow_repository.session.commit()
        await self.workflow_repository.session.refresh(workflow, attribute_names=["steps"])
        await self._audit_workflow(workflow, "workflow.completed", "success")
        return await self._to_read(workflow)

    async def fail_workflow(self, workflow_run_id: UUID, error_message: str, result_summary: dict | None = None) -> WorkflowRunRead:
        workflow = await self._workflow(workflow_run_id)
        self.transition_manager.transition_run(workflow, WorkflowStatus.FAILED)
        workflow.error_message = self.secret_sanitizer.redact_text(error_message) or ""
        workflow.result_summary = self.secret_sanitizer.redact_value(result_summary or workflow.result_summary)
        await self.workflow_repository.session.commit()
        await self.workflow_repository.session.refresh(workflow, attribute_names=["steps"])
        await self._audit_workflow(workflow, "workflow.failed", "failed", error=error_message)
        return await self._to_read(workflow)

    async def cancel_workflow(self, workflow_run_id: UUID) -> WorkflowRunRead:
        workflow = await self._workflow(workflow_run_id)
        self.transition_manager.transition_run(workflow, WorkflowStatus.CANCELLED)
        await self.workflow_repository.session.commit()
        await self.workflow_repository.session.refresh(workflow, attribute_names=["steps"])
        await self._audit_workflow(workflow, "workflow.cancelled", "cancelled")
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
        self.transition_manager.transition_step(step, WorkflowStepStatus.RUNNING)
        await self.step_repository.session.commit()
        await self.step_repository.session.refresh(step)
        return await self._step_to_read(step)

    async def complete_step(self, step_id: UUID, log_output: str | None = None, metadata_json: dict | None = None) -> WorkflowStepRead:
        step = await self._step(step_id)
        self.transition_manager.transition_step(step, WorkflowStepStatus.SUCCESS)
        if log_output:
            step.log_output = self._append_text(step.log_output, self.secret_sanitizer.redact_text(log_output) or "")
        if metadata_json:
            step.metadata_json = {**step.metadata_json, **self.secret_sanitizer.redact_value(metadata_json)}
        await self.step_repository.session.commit()
        await self.step_repository.session.refresh(step)
        return await self._step_to_read(step)

    async def fail_step(
        self,
        step_id: UUID,
        error_output: str,
        log_output: str | None = None,
        metadata_json: dict | None = None,
    ) -> WorkflowStepRead:
        step = await self._step(step_id)
        self.transition_manager.transition_step(step, WorkflowStepStatus.FAILED)
        step.error_output = self._append_text(step.error_output, self.secret_sanitizer.redact_text(error_output) or "")
        if log_output:
            step.log_output = self._append_text(step.log_output, self.secret_sanitizer.redact_text(log_output) or "")
        if metadata_json:
            step.metadata_json = {**step.metadata_json, **self.secret_sanitizer.redact_value(metadata_json)}
        await self.step_repository.session.commit()
        await self.step_repository.session.refresh(step)
        return await self._step_to_read(step)

    async def append_log(self, step_id: UUID, message: str, *, stderr: bool = False) -> WorkflowStepRead:
        step = await self._step(step_id)
        if stderr:
            step.error_output = self._append_text(step.error_output, self.secret_sanitizer.redact_text(message) or "")
        else:
            step.log_output = self._append_text(step.log_output, self.secret_sanitizer.redact_text(message) or "")
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
        step_summary = self.summary_builder.step_summary(steps)
        target_nodes = [item for item in {hostname, *[step.target_hostname for step in steps]} if item]
        current_step = next((step.name for step in steps if step.status == WorkflowStepStatus.RUNNING), None)
        return data.model_copy(
            update={
                "target_hostname": hostname,
                "steps": steps,
                "current_step": current_step,
                "completed_steps": step_summary.success_count,
                "failed_steps": step_summary.failed_count,
                "duration_seconds": duration_seconds(workflow.started_at, workflow.finished_at),
                "target_nodes": target_nodes,
                "linked_job_ids": self.summary_builder.linked_job_ids(steps),
                "activity_timeline": workflow_activity_timeline(workflow, steps),
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

    async def _audit_workflow(
        self,
        workflow: WorkflowRun,
        event_type: str,
        result: str,
        *,
        error: str | None = None,
    ) -> None:
        await self.audit_service.record(
            event_type=event_type,
            actor_username=workflow.initiated_by,
            target_type="workflow_run",
            target_id=workflow.id,
            result=result,
            workflow_run_id=workflow.id,
            metadata={
                "workflow_type": workflow.workflow_type.value,
                "trigger_source": workflow.trigger_source.value,
                "target_server_id": str(workflow.target_server_id) if workflow.target_server_id else None,
            },
            error=error,
        )
