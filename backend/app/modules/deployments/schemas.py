from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.modules.deployments.models import DeploymentStatus
from backend.app.modules.jobs.schemas import JobRead


class DeploymentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    target_server_id: UUID | None = None
    target_server_ids: list[UUID] = Field(default_factory=list)
    compose_content: str = Field(min_length=1, max_length=20000)
    env_content: str | None = Field(default=None, max_length=20000)
    credential_refs: dict[str, str] = Field(default_factory=dict)
    remote_path: str = Field(default="/opt/nexusops/deployments", min_length=1, max_length=500)

    @field_validator("name", "compose_content", "remote_path")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @field_validator("target_server_ids")
    @classmethod
    def dedupe_target_server_ids(cls, value: list[UUID]) -> list[UUID]:
        return list(dict.fromkeys(value))


class DeploymentUpdate(DeploymentCreate):
    pass


class DeploymentRead(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    compose_content: str
    env_content: str | None = None
    credential_refs: dict[str, str] = Field(default_factory=dict)
    status: DeploymentStatus
    target_server_id: UUID | None = None
    target_server_ids: list[UUID] = Field(default_factory=list)
    target_hostname: str | None = None
    targets: list["DeploymentTargetRead"] = Field(default_factory=list)
    latest_execution: "DeploymentExecutionRead | None" = None
    execution_history: list["DeploymentExecutionRead"] = Field(default_factory=list)
    remote_path: str | None = None
    ports: list[str] = Field(default_factory=list)
    compose_source: str = "inline"
    uptime_seconds: int | None = None
    health_state: str = "unknown"
    sync_status: str = "unknown"
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeploymentTargetRead(BaseModel):
    id: UUID
    server_id: UUID
    hostname: str | None = None
    node_type: str | None = None
    environment: str | None = None
    provider: str | None = None
    readiness: str = "unknown"
    remote_path: str
    status: DeploymentStatus
    last_job_id: UUID | None = None
    last_execution: "DeploymentTargetExecutionRead | None" = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeploymentRevisionRead(BaseModel):
    id: UUID
    deployment_id: UUID
    server_id: UUID
    revision_number: int
    operation: str
    job_id: UUID | None = None
    status: DeploymentStatus
    stdout: str | None = None
    stderr: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeploymentTargetExecutionRead(BaseModel):
    id: UUID
    execution_id: UUID
    deployment_id: UUID
    target_id: UUID
    server_id: UUID
    hostname: str | None = None
    status: DeploymentStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: int | None = None
    job_id: UUID | None = None
    revision_id: UUID | None = None
    stdout: str | None = None
    stderr: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeploymentExecutionRead(BaseModel):
    id: UUID
    deployment_id: UUID
    operation: str
    status: DeploymentStatus
    trigger_source: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: int | None = None
    target_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    result_summary: dict = Field(default_factory=dict)
    error_message: str | None = None
    target_executions: list[DeploymentTargetExecutionRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeploymentOperationRead(BaseModel):
    deployment: DeploymentRead
    job: JobRead | None = None
    revision: DeploymentRevisionRead | None = None
    jobs: list[JobRead] = Field(default_factory=list)
    revisions: list[DeploymentRevisionRead] = Field(default_factory=list)
    execution: DeploymentExecutionRead | None = None


class DeploymentStatusRead(BaseModel):
    deployment_id: UUID
    target_server_id: UUID | None = None
    job: JobRead | None = None
    jobs: list[JobRead] = Field(default_factory=list)


class DeploymentLogsRead(BaseModel):
    deployment_id: UUID
    target_server_id: UUID | None = None
    logs: str
    job: JobRead | None = None
    jobs: list[JobRead] = Field(default_factory=list)
