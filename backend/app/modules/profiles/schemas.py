from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.app.modules.jobs.schemas import JobRead
from backend.app.modules.packages.schemas import VariableDefinitionRead


class ProfileStepRead(BaseModel):
    id: str
    name: str
    kind: Literal["action", "package", "command", "deployment", "script", "identity_user", "identity_group", "identity_permission"]
    reference_id: str
    command: str | None = None
    type: Literal["action", "package", "deployment", "script", "identity_user", "identity_group", "identity_permission"] | None = None
    target: str | None = None
    enabled: bool = True
    credential_ref: str | None = None


class InfrastructureProfileRead(BaseModel):
    id: str
    name: str
    category: str
    description: str
    tags: list[str]
    steps: list[ProfileStepRead]
    variables: list[VariableDefinitionRead] = Field(default_factory=list)
    is_builtin: bool = False
    is_modified: bool = False
    base_version: str | None = None
    source_template_id: str | None = None
    modified_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProfileStepWrite(BaseModel):
    id: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    kind: Literal["action", "package", "command", "deployment", "script", "identity_user", "identity_group", "identity_permission"] | None = None
    type: Literal["action", "package", "deployment", "script", "identity_user", "identity_group", "identity_permission"] | None = None
    reference_id: str = Field(default="", max_length=100)
    target: str | None = Field(default=None, max_length=100)
    enabled: bool = True
    credential_ref: str | None = Field(default=None, max_length=255)
    command: str | None = Field(default=None, max_length=8000)

    @field_validator("id", "name")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @model_validator(mode="after")
    def require_reference_or_command(self) -> Self:
        self.kind = self.kind or ("command" if self.type == "script" else self.type)
        self.reference_id = (self.reference_id or self.target or "").strip()
        if self.kind in {"command", "script"}:
            if not self.command or not self.command.strip():
                raise ValueError("Script steps require a command")
            self.id = self.id or f"script-{abs(hash(self.command))}"
            self.name = self.name or "Script"
            self.reference_id = self.reference_id or self.id
            self.command = self.command.strip()
            self.kind = "command"
            self.type = "script"
            return self
        if self.kind not in {"action", "package", "deployment", "identity_user", "identity_group", "identity_permission"}:
            raise ValueError("Step type is required")
        if not self.reference_id:
            raise ValueError("Package, action, deployment, and identity steps require a target")
        self.id = self.id or f"{self.kind}-{self.reference_id}"
        self.name = self.name or self.reference_id
        self.type = self.kind
        return self


class InfrastructureProfileCreate(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=2000)
    tags: list[str] = Field(default_factory=list)
    steps: list[ProfileStepWrite] = Field(min_length=1)
    variables: list[VariableDefinitionRead] = Field(default_factory=list)

    @field_validator("id", "name", "category", "description")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        normalized = []
        seen = set()
        for tag in value:
            clean = tag.strip()
            if clean and clean not in seen:
                normalized.append(clean)
                seen.add(clean)
        return normalized


class InfrastructureProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    tags: list[str] | None = None
    steps: list[ProfileStepWrite] | None = None
    variables: list[VariableDefinitionRead] | None = None

    @field_validator("name", "category", "description")
    @classmethod
    def strip_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = []
        seen = set()
        for tag in value:
            clean = tag.strip()
            if clean and clean not in seen:
                normalized.append(clean)
                seen.add(clean)
        return normalized

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> Self:
        if not self.model_dump(exclude_unset=True):
            raise ValueError("At least one field must be provided")
        return self


class ProfileApplyRequest(BaseModel):
    target_server_id: UUID
    stop_on_failure: bool = True
    variables: dict[str, str] = Field(default_factory=dict)
    credential_refs: dict[str, str] = Field(default_factory=dict)
    execution_credential_ref: str | None = Field(default=None, max_length=255)


class ProfileCloneRequest(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=255)

    @field_validator("id", "name")
    @classmethod
    def strip_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped


class ProfileBulkApplyRequest(BaseModel):
    profile_id: str = Field(min_length=1, max_length=100)
    target_server_ids: list[UUID] = Field(min_length=1)
    stop_on_failure: bool = True
    variables: dict[str, str] = Field(default_factory=dict)
    credential_refs: dict[str, str] = Field(default_factory=dict)
    execution_credential_ref: str | None = Field(default=None, max_length=255)

    @field_validator("profile_id")
    @classmethod
    def strip_profile_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped


class ProfileApplyRead(BaseModel):
    profile_id: str
    target_server_id: UUID
    status: str
    jobs: list[JobRead]
    message: str


class ProfileBulkHostResult(BaseModel):
    target_server_id: UUID
    target_hostname: str | None = None
    success: bool
    result: ProfileApplyRead | None = None
    error: str | None = None


class ProfileBulkApplyRead(BaseModel):
    profile_id: str
    success_count: int
    failure_count: int
    results: list[ProfileBulkHostResult]


class InfrastructureProfileExportRead(BaseModel):
    filename: str
    format: Literal["json", "yaml"]
    content: str


class InfrastructureProfileImportRequest(BaseModel):
    content: str = Field(min_length=1, max_length=120_000)
    format: Literal["json", "yaml"] = "json"
    strategy: Literal["create", "clone_on_conflict"] = "clone_on_conflict"
    clone_suffix: str = Field(default="import", min_length=1, max_length=40)

    @field_validator("clone_suffix")
    @classmethod
    def normalize_clone_suffix(cls, value: str) -> str:
        cleaned = value.strip().strip("-")
        if not cleaned:
            raise ValueError("Clone suffix cannot be blank")
        return cleaned


class InfrastructureProfileImportRead(BaseModel):
    profile: InfrastructureProfileRead
    status: Literal["created", "cloned"]
    warnings: list[str] = Field(default_factory=list)
