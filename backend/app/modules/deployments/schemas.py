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
    remote_path: str | None = None
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


class DeploymentOperationRead(BaseModel):
    deployment: DeploymentRead
    job: JobRead
    revision: DeploymentRevisionRead


class DeploymentStatusRead(BaseModel):
    deployment_id: UUID
    target_server_id: UUID
    job: JobRead


class DeploymentLogsRead(BaseModel):
    deployment_id: UUID
    target_server_id: UUID
    logs: str
    job: JobRead
