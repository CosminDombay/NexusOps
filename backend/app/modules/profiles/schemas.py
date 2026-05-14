from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.app.modules.jobs.schemas import JobRead


class ProfileStepRead(BaseModel):
    id: str
    name: str
    kind: Literal["action", "package"]
    reference_id: str


class InfrastructureProfileRead(BaseModel):
    id: str
    name: str
    category: str
    description: str
    tags: list[str]
    steps: list[ProfileStepRead]
    is_builtin: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProfileStepWrite(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    kind: Literal["action", "package"]
    reference_id: str = Field(min_length=1, max_length=100)

    @field_validator("id", "name", "reference_id")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped


class InfrastructureProfileCreate(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=2000)
    tags: list[str] = Field(default_factory=list)
    steps: list[ProfileStepWrite] = Field(min_length=1)

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


class ProfileBulkApplyRequest(BaseModel):
    profile_id: str = Field(min_length=1, max_length=100)
    target_server_ids: list[UUID] = Field(min_length=1)
    stop_on_failure: bool = True

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
