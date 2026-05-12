from datetime import datetime
from ipaddress import ip_address
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.modules.inventory.models import ServerEnvironment, ServerStatus


class ServerBase(BaseModel):
    hostname: str = Field(min_length=1, max_length=255)
    ip_address: str
    operating_system: str = Field(min_length=1, max_length=150)
    vmid: str | None = Field(default=None, max_length=100)
    environment: ServerEnvironment
    tags: list[str] = Field(default_factory=list)
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_username: str = Field(min_length=1, max_length=100)
    status: ServerStatus = ServerStatus.UNKNOWN
    provider: str = Field(min_length=1, max_length=100)

    @field_validator("ip_address")
    @classmethod
    def validate_ip_address(cls, value: str) -> str:
        return str(ip_address(value))

    @field_validator("hostname", "provider", "ssh_username", "operating_system")
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


class ServerCreate(ServerBase):
    pass


class ServerUpdate(BaseModel):
    hostname: str | None = Field(default=None, min_length=1, max_length=255)
    ip_address: str | None = None
    operating_system: str | None = Field(default=None, min_length=1, max_length=150)
    vmid: str | None = Field(default=None, max_length=100)
    environment: ServerEnvironment | None = None
    tags: list[str] | None = None
    ssh_port: int | None = Field(default=None, ge=1, le=65535)
    ssh_username: str | None = Field(default=None, min_length=1, max_length=100)
    status: ServerStatus | None = None
    provider: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("ip_address")
    @classmethod
    def validate_ip_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(ip_address(value))

    @field_validator("hostname", "provider", "ssh_username", "operating_system")
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


class ServerRead(ServerBase):
    id: UUID
    created_at: datetime
    updated_at: datetime


    model_config = ConfigDict(from_attributes=True)


class ServerListFilters(BaseModel):
    environment: ServerEnvironment | None = None
    provider: str | None = None
    search: str | None = None
