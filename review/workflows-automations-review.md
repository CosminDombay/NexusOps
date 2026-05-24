# Workflows And Automations Review

Generated from the current NexusOps workspace for focused code review.

## backend/app/modules/workflows/models.py

``python
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class WorkflowStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowTriggerSource(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    PROVISIONING = "provisioning"
    SYSTEM = "system"


class WorkflowType(StrEnum):
    PROVISION_VM = "provision_vm"
    PROFILE_EXECUTION = "profile_execution"
    PACKAGE_EXECUTION = "package_execution"
    DEPLOYMENT_EXECUTION = "deployment_execution"
    SCHEDULED_ACTION = "scheduled_action"
    SCHEDULED_PROFILE = "scheduled_profile"
    SCHEDULED_PACKAGE = "scheduled_package"


class WorkflowStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowRun(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workflow_runs"

    workflow_type: Mapped[WorkflowType] = mapped_column(
        Enum(WorkflowType, name="workflow_type", values_callable=lambda enum: [member.value for member in enum]),
        nullable=False,
        index=True,
    )
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, name="workflow_status", values_callable=lambda enum: [member.value for member in enum]),
        default=WorkflowStatus.PENDING,
        nullable=False,
        index=True,
    )
    trigger_source: Mapped[WorkflowTriggerSource] = mapped_column(
        Enum(
            WorkflowTriggerSource,
            name="workflow_trigger_source",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=WorkflowTriggerSource.MANUAL,
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    target_server_id: Mapped[UUID | None] = mapped_column(ForeignKey("servers.id"), nullable=True, index=True)
    initiated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    context_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    result_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    steps: Mapped[list["WorkflowStep"]] = relationship(
        back_populates="workflow_run",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="WorkflowStep.step_order",
    )


class WorkflowStep(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workflow_steps"

    workflow_run_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_runs.id"), nullable=False, index=True)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[WorkflowStepStatus] = mapped_column(
        Enum(
            WorkflowStepStatus,
            name="workflow_step_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=WorkflowStepStatus.PENDING,
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    log_output: Mapped[str] = mapped_column(Text, default="", nullable=False)
    error_output: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    workflow_run: Mapped[WorkflowRun] = relationship(back_populates="steps")

````

## backend/app/modules/workflows/schemas.py

``python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.modules.workflows.models import (
    WorkflowStatus,
    WorkflowStepStatus,
    WorkflowTriggerSource,
    WorkflowType,
)
from backend.app.modules.orchestration.activity import OperationalActivityRead


class WorkflowCreate(BaseModel):
    workflow_type: WorkflowType
    trigger_source: WorkflowTriggerSource = WorkflowTriggerSource.MANUAL
    target_server_id: UUID | None = None
    initiated_by: str | None = Field(default=None, max_length=255)
    context_json: dict = Field(default_factory=dict)


class WorkflowStepCreate(BaseModel):
    step_order: int = Field(ge=1)
    step_type: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    metadata_json: dict = Field(default_factory=dict)


class WorkflowStepRead(BaseModel):
    id: UUID
    workflow_run_id: UUID
    step_order: int
    step_type: str
    name: str
    status: WorkflowStepStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    log_output: str = ""
    error_output: str = ""
    metadata_json: dict = Field(default_factory=dict)
    target_hostname: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowRunRead(BaseModel):
    id: UUID
    workflow_type: WorkflowType
    status: WorkflowStatus
    trigger_source: WorkflowTriggerSource
    started_at: datetime | None = None
    finished_at: datetime | None = None
    target_server_id: UUID | None = None
    target_hostname: str | None = None
    initiated_by: str | None = None
    context_json: dict = Field(default_factory=dict)
    result_summary: dict = Field(default_factory=dict)
    error_message: str | None = None
    steps: list[WorkflowStepRead] = Field(default_factory=list)
    current_step: str | None = None
    completed_steps: int = 0
    failed_steps: int = 0
    duration_seconds: int | None = None
    target_nodes: list[str] = Field(default_factory=list)
    linked_job_ids: list[str] = Field(default_factory=list)
    activity_timeline: list[OperationalActivityRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

````

## backend/app/modules/workflows/repository.py

``python
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

````

## backend/app/modules/workflows/service.py

``python
from datetime import UTC, datetime
from uuid import UUID

from backend.app.modules.audit.repository import AuditEventRepository
from backend.app.modules.audit.service import AuditService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.orchestration.activity import workflow_activity_timeline
from backend.app.modules.orchestration.utils import duration_seconds, summarize_statuses
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
        audit_service: AuditService | None = None,
    ) -> None:
        self.workflow_repository = workflow_repository
        self.step_repository = step_repository
        self.server_repository = server_repository
        self.audit_service = audit_service or AuditService(AuditEventRepository(workflow_repository.session))

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
        workflow.status = WorkflowStatus.QUEUED
        await self.workflow_repository.session.commit()
        await self.workflow_repository.session.refresh(workflow, attribute_names=["steps"])
        await self._audit_workflow(workflow, "workflow.queued", "success")
        return await self._to_read(workflow)

    async def start_workflow(self, workflow_run_id: UUID) -> WorkflowRunRead:
        workflow = await self._workflow(workflow_run_id)
        if workflow.status == WorkflowStatus.CANCELLED:
            raise WorkflowInvalidTransitionError("Cancelled workflow cannot be started")
        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = workflow.started_at or datetime.now(UTC)
        await self.workflow_repository.session.commit()
        await self.workflow_repository.session.refresh(workflow, attribute_names=["steps"])
        await self._audit_workflow(workflow, "workflow.started", "success")
        return await self._to_read(workflow)

    async def complete_workflow(self, workflow_run_id: UUID, result_summary: dict | None = None) -> WorkflowRunRead:
        workflow = await self._workflow(workflow_run_id)
        workflow.status = WorkflowStatus.SUCCESS
        workflow.finished_at = datetime.now(UTC)
        workflow.result_summary = result_summary or workflow.result_summary
        await self.workflow_repository.session.commit()
        await self.workflow_repository.session.refresh(workflow, attribute_names=["steps"])
        await self._audit_workflow(workflow, "workflow.completed", "success")
        return await self._to_read(workflow)

    async def fail_workflow(self, workflow_run_id: UUID, error_message: str, result_summary: dict | None = None) -> WorkflowRunRead:
        workflow = await self._workflow(workflow_run_id)
        workflow.status = WorkflowStatus.FAILED
        workflow.finished_at = datetime.now(UTC)
        workflow.error_message = error_message
        workflow.result_summary = result_summary or workflow.result_summary
        await self.workflow_repository.session.commit()
        await self.workflow_repository.session.refresh(workflow, attribute_names=["steps"])
        await self._audit_workflow(workflow, "workflow.failed", "failed", error=error_message)
        return await self._to_read(workflow)

    async def cancel_workflow(self, workflow_run_id: UUID) -> WorkflowRunRead:
        workflow = await self._workflow(workflow_run_id)
        workflow.status = WorkflowStatus.CANCELLED
        workflow.finished_at = datetime.now(UTC)
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

    async def fail_step(
        self,
        step_id: UUID,
        error_output: str,
        log_output: str | None = None,
        metadata_json: dict | None = None,
    ) -> WorkflowStepRead:
        step = await self._step(step_id)
        step.status = WorkflowStepStatus.FAILED
        step.finished_at = datetime.now(UTC)
        step.error_output = self._append_text(step.error_output, error_output)
        if log_output:
            step.log_output = self._append_text(step.log_output, log_output)
        if metadata_json:
            step.metadata_json = {**step.metadata_json, **metadata_json}
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
        step_summary = summarize_statuses(
            steps,
            success_states={WorkflowStepStatus.SUCCESS},
            failure_states={WorkflowStepStatus.FAILED},
        )
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
                "completed_steps": step_summary.success_count,
                "failed_steps": step_summary.failed_count,
                "duration_seconds": duration_seconds(workflow.started_at, workflow.finished_at),
                "target_nodes": target_nodes,
                "linked_job_ids": sorted(set(linked_job_ids)),
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

````

## backend/app/modules/workflows/router.py

``python
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db_session
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.workflows.repository import WorkflowRunRepository, WorkflowStepRepository
from backend.app.modules.workflows.schemas import WorkflowRunRead
from backend.app.modules.workflows.service import WorkflowNotFoundError, WorkflowService

router = APIRouter()


async def get_workflow_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> WorkflowService:
    return WorkflowService(
        workflow_repository=WorkflowRunRepository(session),
        step_repository=WorkflowStepRepository(session),
        server_repository=ServerRepository(session),
    )


@router.get("", response_model=list[WorkflowRunRead])
async def list_workflows(
    service: Annotated[WorkflowService, Depends(get_workflow_service)],
    target_server_id: UUID | None = None,
) -> list[WorkflowRunRead]:
    return await service.list_workflows(target_server_id=target_server_id)


@router.get("/{workflow_run_id}", response_model=WorkflowRunRead)
async def get_workflow(
    workflow_run_id: UUID,
    service: Annotated[WorkflowService, Depends(get_workflow_service)],
) -> WorkflowRunRead:
    try:
        return await service.get_workflow(workflow_run_id)
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

````

## backend/app/modules/automations/models.py

``python
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class AutomationScheduleType(StrEnum):
    INTERVAL = "interval"
    CRON = "cron"


class AutomationTargetMode(StrEnum):
    SINGLE_HOST = "single_host"
    MULTIPLE_HOSTS = "multiple_hosts"


class AutomationOperationType(StrEnum):
    ACTION = "action"
    PROFILE = "profile"
    PACKAGE = "package"
    DEPLOYMENT = "deployment"
    COMMAND = "command"


class Automation(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "automations"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    schedule_type: Mapped[AutomationScheduleType] = mapped_column(
        Enum(
            AutomationScheduleType,
            name="automation_schedule_type",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    cron_expression: Mapped[str | None] = mapped_column(String(120), nullable=True)
    interval_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_mode: Mapped[AutomationTargetMode] = mapped_column(
        Enum(
            AutomationTargetMode,
            name="automation_target_mode",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    target_server_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    operation_type: Mapped[AutomationOperationType] = mapped_column(
        Enum(
            AutomationOperationType,
            name="automation_operation_type",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        index=True,
    )
    reference_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_command: Mapped[str | None] = mapped_column(Text, nullable=True)
    variables_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    credential_refs: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(50), nullable=True)

````

## backend/app/modules/automations/schemas.py

``python
from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.modules.automations.models import (
    AutomationOperationType,
    AutomationScheduleType,
    AutomationTargetMode,
)
from backend.app.modules.workflows.schemas import WorkflowRunRead


class AutomationTargetRead(BaseModel):
    id: str
    hostname: str
    node_type: str
    environment: str
    provider: str
    source: str
    tags: list[str] = Field(default_factory=list)


class AutomationBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    enabled: bool = True
    schedule_type: AutomationScheduleType
    cron_expression: str | None = Field(default=None, max_length=120)
    interval_seconds: int | None = Field(default=None, gt=0)
    target_mode: AutomationTargetMode
    target_server_ids: list[UUID] = Field(default_factory=list, min_length=1)
    operation_type: AutomationOperationType
    reference_id: str | None = Field(default=None, max_length=255)
    raw_command: str | None = Field(default=None, max_length=8000)
    variables_json: dict[str, str] = Field(default_factory=dict)
    credential_refs: dict[str, str] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @field_validator("cron_expression", "reference_id", "raw_command")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def validate_schedule_and_operation(self) -> Self:
        if self.schedule_type == AutomationScheduleType.INTERVAL and not self.interval_seconds:
            raise ValueError("Interval automations require interval_seconds")
        if self.schedule_type == AutomationScheduleType.CRON:
            if not self.cron_expression:
                raise ValueError("Cron automations require cron_expression")
            if len(self.cron_expression.split()) != 5:
                raise ValueError("Cron expression must use five fields")
        if self.operation_type in {
            AutomationOperationType.ACTION,
            AutomationOperationType.PROFILE,
            AutomationOperationType.PACKAGE,
            AutomationOperationType.DEPLOYMENT,
        } and not self.reference_id:
            raise ValueError("Referenced automation operations require reference_id")
        if self.operation_type == AutomationOperationType.COMMAND and not self.raw_command:
            raise ValueError("Command automations require raw_command")
        return self


class AutomationCreate(AutomationBase):
    pass


class AutomationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    enabled: bool | None = None
    schedule_type: AutomationScheduleType | None = None
    cron_expression: str | None = Field(default=None, max_length=120)
    interval_seconds: int | None = Field(default=None, gt=0)
    target_mode: AutomationTargetMode | None = None
    target_server_ids: list[UUID] | None = None
    operation_type: AutomationOperationType | None = None
    reference_id: str | None = Field(default=None, max_length=255)
    raw_command: str | None = Field(default=None, max_length=8000)
    variables_json: dict[str, str] | None = None
    credential_refs: dict[str, str] | None = None

    @field_validator("name", "cron_expression", "reference_id", "raw_command")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> Self:
        if not self.model_dump(exclude_unset=True):
            raise ValueError("At least one field must be provided")
        return self


class AutomationRead(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    enabled: bool
    schedule_type: AutomationScheduleType
    cron_expression: str | None = None
    interval_seconds: int | None = None
    target_mode: AutomationTargetMode
    target_server_ids: list[str]
    operation_type: AutomationOperationType
    reference_id: str | None = None
    raw_command: str | None = None
    variables_json: dict = Field(default_factory=dict)
    credential_refs: dict = Field(default_factory=dict)
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    last_status: str | None = None
    runtime_state: str = "idle"
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_duration_seconds: int | None = None
    execution_count: int = 0
    target_nodes: list[AutomationTargetRead] = Field(default_factory=list)
    recent_executions: list[WorkflowRunRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

````

## backend/app/modules/automations/repository.py

``python
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from backend.app.common.repository import BaseRepository
from backend.app.modules.automations.models import Automation


class AutomationRepository(BaseRepository[Automation]):
    async def create(self, automation: Automation) -> Automation:
        self.session.add(automation)
        await self.session.flush()
        await self.session.refresh(automation)
        return automation

    async def get_by_id(self, automation_id: UUID) -> Automation | None:
        result = await self.session.execute(select(Automation).where(Automation.id == automation_id))
        return result.scalar_one_or_none()

    async def list(self) -> list[Automation]:
        result = await self.session.execute(select(Automation).order_by(Automation.created_at.desc()))
        return list(result.scalars().all())

    async def list_for_target(self, target_server_id: UUID) -> list[Automation]:
        automations = await self.list()
        return [
            automation
            for automation in automations
            if str(target_server_id) in {str(item) for item in automation.target_server_ids}
        ]

    async def list_enabled(self) -> list[Automation]:
        result = await self.session.execute(
            select(Automation).where(Automation.enabled.is_(True)).order_by(Automation.name.asc())
        )
        return list(result.scalars().all())

    async def delete(self, automation: Automation) -> None:
        await self.session.delete(automation)

````

## backend/app/modules/automations/service.py

``python
from datetime import UTC, datetime
from uuid import UUID

from backend.app.modules.automations.models import Automation, AutomationOperationType
from backend.app.modules.automations.repository import AutomationRepository
from backend.app.modules.automations.schemas import AutomationCreate, AutomationRead, AutomationTargetRead, AutomationUpdate
from backend.app.modules.inventory.models import InventoryLifecycleState
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.jobs.schemas import JobActionExecuteRequest
from backend.app.modules.jobs.service import JobService
from backend.app.modules.orchestration.semantics import workflow_failure_states, workflow_runtime_state
from backend.app.modules.packages.schemas import PackageExecuteRequest
from backend.app.modules.packages.service import PackageAutomationService
from backend.app.modules.profiles.schemas import ProfileApplyRequest
from backend.app.modules.profiles.service import ProfileService
from backend.app.modules.workflows.models import WorkflowStatus, WorkflowTriggerSource, WorkflowType
from backend.app.modules.workflows.schemas import WorkflowCreate, WorkflowStepCreate
from backend.app.modules.workflows.service import WorkflowService


class AutomationNotFoundError(Exception):
    """Raised when an automation cannot be found."""


class AutomationValidationError(Exception):
    """Raised when automation configuration is invalid."""


class AutomationService:
    def __init__(
        self,
        *,
        repository: AutomationRepository,
        server_repository: ServerRepository,
        workflow_service: WorkflowService,
        job_service: JobService | None = None,
        profile_service: ProfileService | None = None,
        package_service: PackageAutomationService | None = None,
    ) -> None:
        self.repository = repository
        self.server_repository = server_repository
        self.workflow_service = workflow_service
        self.job_service = job_service
        self.profile_service = profile_service
        self.package_service = package_service

    async def list_automations(self, *, target_server_id: UUID | None = None) -> list[AutomationRead]:
        automations = (
            await self.repository.list_for_target(target_server_id)
            if target_server_id is not None
            else await self.repository.list()
        )
        workflows = await self.workflow_service.list_workflows(target_server_id=target_server_id)
        servers = await self.server_repository.list(include_inactive=True)
        return [
            self._to_read(
                automation,
                workflows=[workflow for workflow in workflows if workflow.context_json.get("automation_id") == str(automation.id)],
                servers=servers,
            )
            for automation in automations
        ]

    async def create_automation(self, payload: AutomationCreate) -> AutomationRead:
        self._validate_supported_operation(payload.operation_type)
        await self._validate_targets([str(item) for item in payload.target_server_ids])
        automation = await self.repository.create(
            Automation(
                name=payload.name,
                description=payload.description,
                enabled=payload.enabled,
                schedule_type=payload.schedule_type,
                cron_expression=payload.cron_expression,
                interval_seconds=payload.interval_seconds,
                target_mode=payload.target_mode,
                target_server_ids=[str(item) for item in payload.target_server_ids],
                operation_type=payload.operation_type,
                reference_id=payload.reference_id,
                raw_command=payload.raw_command,
                variables_json=payload.variables_json,
                credential_refs=payload.credential_refs,
            )
        )
        await self.repository.session.commit()
        return self._to_read(automation)

    async def update_automation(self, automation_id: UUID, payload: AutomationUpdate) -> AutomationRead:
        automation = await self._automation(automation_id)
        update_data = payload.model_dump(exclude_unset=True)
        if "operation_type" in update_data and update_data["operation_type"] is not None:
            self._validate_supported_operation(update_data["operation_type"])
        if "target_server_ids" in update_data and update_data["target_server_ids"] is not None:
            update_data["target_server_ids"] = [str(item) for item in update_data["target_server_ids"]]
            await self._validate_targets(update_data["target_server_ids"])
        for key, value in update_data.items():
            setattr(automation, key, value)
        await self.repository.session.commit()
        await self.repository.session.refresh(automation)
        return self._to_read(automation)

    async def delete_automation(self, automation_id: UUID) -> None:
        automation = await self._automation(automation_id)
        await self.repository.delete(automation)
        await self.repository.session.commit()

    async def enable_automation(self, automation_id: UUID) -> AutomationRead:
        automation = await self._automation(automation_id)
        automation.enabled = True
        await self.repository.session.commit()
        await self.repository.session.refresh(automation)
        return self._to_read(automation)

    async def disable_automation(self, automation_id: UUID) -> AutomationRead:
        automation = await self._automation(automation_id)
        automation.enabled = False
        await self.repository.session.commit()
        await self.repository.session.refresh(automation)
        return self._to_read(automation)

    async def create_run_workflow(
        self,
        automation_id: UUID,
        *,
        trigger_source: WorkflowTriggerSource = WorkflowTriggerSource.MANUAL,
    ):
        automation = await self._automation(automation_id)
        target_server_id = UUID(automation.target_server_ids[0]) if automation.target_server_ids else None
        workflow_type = {
            AutomationOperationType.ACTION: WorkflowType.SCHEDULED_ACTION,
            AutomationOperationType.PROFILE: WorkflowType.SCHEDULED_PROFILE,
            AutomationOperationType.PACKAGE: WorkflowType.SCHEDULED_PACKAGE,
        }.get(automation.operation_type)
        if workflow_type is None:
            raise AutomationValidationError("Only action, profile, and package automations are supported initially")

        workflow = await self.workflow_service.create_workflow(
            WorkflowCreate(
                workflow_type=workflow_type,
                trigger_source=trigger_source,
                target_server_id=target_server_id,
                context_json={"automation_id": str(automation.id), "automation_name": automation.name},
            )
        )
        await self.workflow_service.mark_queued(workflow.id)
        return workflow

    async def execute_automation_workflow(self, automation_id: UUID, workflow_run_id: UUID) -> None:
        automation = await self._automation(automation_id)
        await self.workflow_service.start_workflow(workflow_run_id)
        status = WorkflowStatus.SUCCESS
        result_summary: dict[str, object] = {"automation_id": str(automation.id), "jobs": []}

        try:
            for index, server_id in enumerate(automation.target_server_ids, start=1):
                step = await self.workflow_service.add_step(
                    workflow_run_id,
                    WorkflowStepCreate(
                        step_order=index,
                        step_type=automation.operation_type.value,
                        name=f"{automation.name} on {server_id}",
                        metadata_json={"target_server_id": server_id},
                    ),
                )
                await self.workflow_service.start_step(step.id)
                try:
                    jobs = await self._execute_operation(automation, UUID(server_id))
                    result_summary["jobs"] = [*result_summary["jobs"], *[str(job.id) for job in jobs]]
                    await self.workflow_service.complete_step(
                        step.id,
                        log_output="\n".join((job.stdout or "").strip() for job in jobs if job.stdout),
                        metadata_json={"job_ids": [str(job.id) for job in jobs]},
                    )
                except Exception as exc:
                    status = WorkflowStatus.FAILED
                    await self.workflow_service.fail_step(step.id, str(exc))
                    raise
            await self.workflow_service.complete_workflow(workflow_run_id, result_summary=result_summary)
        except Exception as exc:
            await self.workflow_service.fail_workflow(workflow_run_id, str(exc), result_summary=result_summary)
        finally:
            automation.last_run_at = datetime.now(UTC)
            automation.last_status = status.value
            await self.repository.session.commit()

    async def _execute_operation(self, automation: Automation, target_server_id: UUID):
        if automation.operation_type == AutomationOperationType.ACTION:
            if self.job_service is None:
                raise AutomationValidationError("Job service is required for action automations")
            job = await self.job_service.execute_action(
                JobActionExecuteRequest(
                    target_server_id=target_server_id,
                    action_id=automation.reference_id or "",
                )
            )
            return [job]

        if automation.operation_type == AutomationOperationType.PACKAGE:
            if self.package_service is None:
                raise AutomationValidationError("Package service is required for package automations")
            job = await self.package_service.execute_definition(
                automation.reference_id or "",
                PackageExecuteRequest(
                    target_server_id=target_server_id,
                    variables=automation.variables_json,
                    credential_refs=automation.credential_refs,
                ),
            )
            return [job]

        if automation.operation_type == AutomationOperationType.PROFILE:
            if self.profile_service is None:
                raise AutomationValidationError("Profile service is required for profile automations")
            result = await self.profile_service.apply_profile(
                automation.reference_id or "",
                ProfileApplyRequest(
                    target_server_id=target_server_id,
                    variables=automation.variables_json,
                    credential_refs=automation.credential_refs,
                ),
            )
            return result.jobs

        raise AutomationValidationError("Only action, profile, and package automations are supported initially")

    async def _validate_targets(self, server_ids: list[str]) -> None:
        for server_id in server_ids:
            server = await self.server_repository.get_by_id(UUID(server_id))
            if server is None:
                raise AutomationValidationError(f"Target server not found: {server_id}")
            if not server.managed or server.lifecycle_state == InventoryLifecycleState.ARCHIVED:
                raise AutomationValidationError(f"Target server is not executable: {server.hostname}")

    async def _automation(self, automation_id: UUID) -> Automation:
        automation = await self.repository.get_by_id(automation_id)
        if automation is None:
            raise AutomationNotFoundError("Automation not found")
        return automation

    @staticmethod
    def _validate_supported_operation(operation_type: AutomationOperationType) -> None:
        if operation_type not in {
            AutomationOperationType.ACTION,
            AutomationOperationType.PROFILE,
            AutomationOperationType.PACKAGE,
        }:
            raise AutomationValidationError("Only action, profile, and package automations are supported initially")

    def _to_read(self, automation: Automation, *, workflows=None, servers=None) -> AutomationRead:
        workflows = sorted(workflows or [], key=lambda item: item.created_at, reverse=True)
        servers = servers or []
        target_nodes = []
        for server_id in automation.target_server_ids:
            server = next((item for item in servers if str(item.id) == str(server_id)), None)
            if server:
                target_nodes.append(
                    AutomationTargetRead(
                        id=str(server.id),
                        hostname=server.hostname,
                        node_type=server.node_type.value,
                        environment=server.environment.value,
                        provider=server.provider,
                        source=server.source,
                        tags=server.tags,
                    )
                )
        last_success = next((workflow for workflow in workflows if workflow.status == WorkflowStatus.SUCCESS), None)
        last_failure = next((workflow for workflow in workflows if workflow.status in workflow_failure_states()), None)
        recent = workflows[:5]
        last = recent[0] if recent else None
        runtime_state = "disabled" if not automation.enabled else "idle"
        if automation.enabled and last:
            runtime_state = workflow_runtime_state(last.status)

        return AutomationRead.model_validate(automation).model_copy(
            update={
                "runtime_state": runtime_state,
                "last_success_at": last_success.finished_at if last_success else None,
                "last_failure_at": last_failure.finished_at if last_failure else None,
                "last_duration_seconds": last.duration_seconds if last else None,
                "execution_count": len(workflows),
                "target_nodes": target_nodes,
                "recent_executions": recent,
            }
        )

````

## backend/app/modules/automations/router.py

``python
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db_session
from backend.app.modules.automations.factory import build_automation_service
from backend.app.modules.automations.schemas import AutomationCreate, AutomationRead, AutomationUpdate
from backend.app.modules.automations.service import AutomationNotFoundError, AutomationService, AutomationValidationError
from backend.app.modules.automations.tasks import execute_automation_workflow
from backend.app.modules.workflows.schemas import WorkflowRunRead
from backend.app.workers.queue.service import task_queue
from backend.app.workers.scheduler.service import scheduler_service

router = APIRouter()


async def get_automation_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AutomationService:
    return build_automation_service(session)


@router.get("", response_model=list[AutomationRead])
async def list_automations(
    service: Annotated[AutomationService, Depends(get_automation_service)],
    target_server_id: UUID | None = None,
) -> list[AutomationRead]:
    return await service.list_automations(target_server_id=target_server_id)


@router.post("", response_model=AutomationRead, status_code=status.HTTP_201_CREATED)
async def create_automation(
    payload: AutomationCreate,
    service: Annotated[AutomationService, Depends(get_automation_service)],
) -> AutomationRead:
    try:
        automation = await service.create_automation(payload)
        await scheduler_service.reload_automations()
        return automation
    except AutomationValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.put("/{automation_id}", response_model=AutomationRead)
async def update_automation(
    automation_id: UUID,
    payload: AutomationUpdate,
    service: Annotated[AutomationService, Depends(get_automation_service)],
) -> AutomationRead:
    try:
        automation = await service.update_automation(automation_id, payload)
        await scheduler_service.reload_automations()
        return automation
    except AutomationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AutomationValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.delete("/{automation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_automation(
    automation_id: UUID,
    service: Annotated[AutomationService, Depends(get_automation_service)],
) -> None:
    try:
        await service.delete_automation(automation_id)
        await scheduler_service.reload_automations()
    except AutomationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{automation_id}/enable", response_model=AutomationRead)
async def enable_automation(
    automation_id: UUID,
    service: Annotated[AutomationService, Depends(get_automation_service)],
) -> AutomationRead:
    try:
        automation = await service.enable_automation(automation_id)
        await scheduler_service.reload_automations()
        return automation
    except AutomationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{automation_id}/disable", response_model=AutomationRead)
async def disable_automation(
    automation_id: UUID,
    service: Annotated[AutomationService, Depends(get_automation_service)],
) -> AutomationRead:
    try:
        automation = await service.disable_automation(automation_id)
        await scheduler_service.reload_automations()
        return automation
    except AutomationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{automation_id}/run", response_model=WorkflowRunRead, status_code=status.HTTP_202_ACCEPTED)
async def run_automation(
    automation_id: UUID,
    service: Annotated[AutomationService, Depends(get_automation_service)],
) -> WorkflowRunRead:
    try:
        workflow = await service.create_run_workflow(automation_id)
        task_queue.submit(
            execute_automation_workflow(automation_id, workflow.id),
            name=f"automation:{automation_id}",
            owner="api",
            execution_origin="automation",
            correlation_id=str(workflow.id),
        )
        return workflow
    except AutomationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AutomationValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

````

## backend/app/modules/automations/factory.py

``python
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.ssh import ParamikoSshAdapter
from backend.app.db.session import AsyncSessionLocal
from backend.app.modules.audit.repository import AuditEventRepository
from backend.app.modules.audit.service import AuditService
from backend.app.modules.automations.repository import AutomationRepository
from backend.app.modules.automations.service import AutomationService
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.deployments.repository import DeploymentRepository, DeploymentRevisionRepository, DeploymentTargetRepository
from backend.app.modules.deployments.service import DockerComposeDeploymentService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.jobs.repository import CustomOperationalActionRepository, JobRepository
from backend.app.modules.jobs.service import JobService
from backend.app.modules.packages.repository import PackageDefinitionRepository
from backend.app.modules.packages.service import PackageAutomationService
from backend.app.modules.profiles.repository import InfrastructureProfileRepository
from backend.app.modules.profiles.service import ProfileService
from backend.app.modules.workflows.repository import WorkflowRunRepository, WorkflowStepRepository
from backend.app.modules.workflows.service import WorkflowService


def build_automation_service(session: AsyncSession) -> AutomationService:
    credential_service = CredentialService(repository=CredentialRepository(session))
    server_repository = ServerRepository(session)
    job_service = JobService(
        job_repository=JobRepository(session),
        server_repository=server_repository,
        ssh_adapter=ParamikoSshAdapter(),
        action_repository=CustomOperationalActionRepository(session),
        credential_service=credential_service,
        audit_service=AuditService(AuditEventRepository(session)),
        session_factory=AsyncSessionLocal,
    )
    audit_service = AuditService(AuditEventRepository(session))
    workflow_service = WorkflowService(
        workflow_repository=WorkflowRunRepository(session),
        step_repository=WorkflowStepRepository(session),
        server_repository=server_repository,
        audit_service=audit_service,
    )
    package_repository = PackageDefinitionRepository(session)
    deployment_service = DockerComposeDeploymentService(
        repository=DeploymentRepository(session),
        target_repository=DeploymentTargetRepository(session),
        revision_repository=DeploymentRevisionRepository(session),
        server_repository=server_repository,
        job_service=job_service,
        credential_service=credential_service,
    )
    profile_service = ProfileService(
        job_service=job_service,
        repository=InfrastructureProfileRepository(session),
        package_repository=package_repository,
        deployment_service=deployment_service,
        workflow_service=workflow_service,
    )
    package_service = PackageAutomationService(
        repository=package_repository,
        job_service=job_service,
        credential_service=credential_service,
    )
    return AutomationService(
        repository=AutomationRepository(session),
        server_repository=server_repository,
        workflow_service=workflow_service,
        job_service=job_service,
        profile_service=profile_service,
        package_service=package_service,
    )

````

## backend/app/modules/automations/tasks.py

``python
from uuid import UUID

from backend.app.db.session import AsyncSessionLocal
from backend.app.modules.automations.factory import build_automation_service


async def execute_automation_workflow(automation_id: UUID, workflow_run_id: UUID) -> None:
    async with AsyncSessionLocal() as session:
        service = build_automation_service(session)
        await service.execute_automation_workflow(automation_id, workflow_run_id)

````

