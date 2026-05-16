from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class VariableDefinitionRead(BaseModel):
    name: str
    description: str = ""
    default_value: str | None = None
    required: bool = False
    sensitive: bool = False
    credential_type: str | None = None


class PackageDefinitionRead(BaseModel):
    id: str
    name: str
    category: str
    supported_os: list[str]
    install_command: str
    uninstall_command: str = ""
    validation_command: str
    variables: list[VariableDefinitionRead] = Field(default_factory=list)
    tags: list[str]
    description: str
    is_builtin: bool = False
    is_modified: bool = False
    base_version: str | None = None
    source_template_id: str | None = None
    modified_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PackageDefinitionCreate(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=100)
    supported_os: list[str] = Field(default_factory=list)
    install_command: str = Field(min_length=1, max_length=8000)
    uninstall_command: str = Field(default="", max_length=8000)
    validation_command: str = Field(min_length=1, max_length=8000)
    variables: list[VariableDefinitionRead] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    description: str = Field(min_length=1, max_length=2000)

    @field_validator("id", "name", "category", "install_command", "validation_command", "description")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @field_validator("supported_os", "tags")
    @classmethod
    def normalize_list(cls, value: list[str]) -> list[str]:
        normalized = []
        seen = set()
        for item in value:
            clean = item.strip()
            if clean and clean not in seen:
                normalized.append(clean)
                seen.add(clean)
        return normalized


class PackageDefinitionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    supported_os: list[str] | None = None
    install_command: str | None = Field(default=None, min_length=1, max_length=8000)
    uninstall_command: str | None = Field(default=None, max_length=8000)
    validation_command: str | None = Field(default=None, min_length=1, max_length=8000)
    variables: list[VariableDefinitionRead] | None = None
    tags: list[str] | None = None
    description: str | None = Field(default=None, min_length=1, max_length=2000)

    @field_validator("name", "category", "install_command", "validation_command", "description")
    @classmethod
    def strip_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @field_validator("supported_os", "tags")
    @classmethod
    def normalize_list(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = []
        seen = set()
        for item in value:
            clean = item.strip()
            if clean and clean not in seen:
                normalized.append(clean)
                seen.add(clean)
        return normalized

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> Self:
        if not self.model_dump(exclude_unset=True):
            raise ValueError("At least one field must be provided")
        return self


class PackageExecuteRequest(BaseModel):
    target_server_id: UUID
    variables: dict[str, str] = Field(default_factory=dict)
    credential_refs: dict[str, str] = Field(default_factory=dict)


class PackageCloneRequest(BaseModel):
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


class PackageBulkApplyRequest(BaseModel):
    package_id: str = Field(min_length=1, max_length=100)
    target_server_ids: list[UUID] = Field(min_length=1)
    variables: dict[str, str] = Field(default_factory=dict)
    credential_refs: dict[str, str] = Field(default_factory=dict)

    @field_validator("package_id")
    @classmethod
    def strip_package_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped


class PackageDefinitionRecordRead(PackageDefinitionRead):
    model_config = ConfigDict(from_attributes=True)
