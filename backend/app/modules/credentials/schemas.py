from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

CredentialType = Literal["password", "ssh_password", "ssh_key", "api_token", "env_secret"]
CredentialScope = Literal["global", "project", "environment"]


class CredentialBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    credential_type: CredentialType
    username: str | None = Field(default=None, max_length=100)
    tags: list[str] = Field(default_factory=list)
    scope: CredentialScope = "global"

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @field_validator("description", "username")
    @classmethod
    def strip_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

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


class CredentialCreate(CredentialBase):
    secret: str | None = Field(default=None, max_length=20000)
    private_key: str | None = Field(default=None, max_length=50000)
    passphrase: str | None = Field(default=None, max_length=20000)

    @model_validator(mode="after")
    def require_secret_material(self) -> Self:
        if self.credential_type in {"password", "ssh_password", "api_token", "env_secret"} and not self.secret:
            raise ValueError("Secret value is required for this credential type")
        if self.credential_type == "ssh_key" and not self.private_key:
            raise ValueError("Private key is required for ssh_key credentials")
        return self


class CredentialUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    credential_type: CredentialType | None = None
    username: str | None = Field(default=None, max_length=100)
    secret: str | None = Field(default=None, max_length=20000)
    private_key: str | None = Field(default=None, max_length=50000)
    passphrase: str | None = Field(default=None, max_length=20000)
    tags: list[str] | None = None
    scope: CredentialScope | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @field_validator("description", "username", "secret", "private_key", "passphrase")
    @classmethod
    def strip_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return [tag.strip() for tag in value if tag.strip()]

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> Self:
        if not self.model_dump(exclude_unset=True):
            raise ValueError("At least one field must be provided")
        return self


class CredentialRead(BaseModel):
    id: UUID
    name: str
    description: str
    credential_type: CredentialType
    username: str | None = None
    masked_secret: str = "********"
    tags: list[str]
    scope: CredentialScope
    deleted_at: datetime | None = None
    deleted_by: str | None = None
    delete_reason: str | None = None
    reference_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CredentialDeleteRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class CredentialReferenceRead(BaseModel):
    reference_type: str
    reference_id: str
    name: str
    field: str
    detail: str | None = None


class CredentialUsageRead(BaseModel):
    credential_id: UUID
    references: list[CredentialReferenceRead] = Field(default_factory=list)

    @computed_field
    @property
    def reference_count(self) -> int:
        return len(self.references)


class ResolvedCredential(BaseModel):
    id: UUID
    name: str
    credential_type: str
    username: str | None = None
    secret: str | None = None
    private_key: str | None = None
    passphrase: str | None = None
