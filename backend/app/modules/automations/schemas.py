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
