from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.modules.workflows.models import (
    WorkflowStatus,
    WorkflowStepStatus,
    WorkflowTriggerSource,
    WorkflowType,
)


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
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
