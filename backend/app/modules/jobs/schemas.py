from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.modules.jobs.models import JobStatus


class JobExecuteRequest(BaseModel):
    target_server_id: UUID
    command: str = Field(min_length=1, max_length=20000)
    operation_type: str = Field(default="command", min_length=1, max_length=100)

    @field_validator("command", "operation_type")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped


class JobBulkExecuteRequest(BaseModel):
    target_server_ids: list[UUID] = Field(min_length=1)
    command: str = Field(min_length=1, max_length=20000)
    operation_type: str = Field(default="command", min_length=1, max_length=100)

    @field_validator("command", "operation_type")
    @classmethod
    def strip_bulk_required_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped


class OperationalActionRead(BaseModel):
    id: str
    name: str
    category: str
    description: str
    command: str
    destructive: bool = False


class JobActionExecuteRequest(BaseModel):
    target_server_id: UUID
    action_id: str = Field(min_length=1, max_length=100)

    @field_validator("action_id")
    @classmethod
    def strip_action_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped


class JobRead(BaseModel):
    id: UUID
    target_server_id: UUID
    target_hostname: str | None = None
    operation_type: str
    command: str
    status: JobStatus
    stdout: str | None = None
    stderr: str | None = None
    exit_code: int | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BulkExecutionHostResult(BaseModel):
    target_server_id: UUID
    target_hostname: str | None = None
    success: bool
    job: JobRead | None = None
    error: str | None = None


class BulkExecutionRead(BaseModel):
    operation_type: str
    success_count: int
    failure_count: int
    results: list[BulkExecutionHostResult]
