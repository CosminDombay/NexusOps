from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.modules.integrations.models import IntegrationType


class IntegrationBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: IntegrationType
    enabled: bool = True
    config: dict[str, object] = Field(default_factory=dict)
    credential_refs: dict[str, str] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @model_validator(mode="after")
    def validate_known_config(self) -> Self:
        validate_integration_config(self.name, self.config)
        return self


class IntegrationCreate(IntegrationBase):
    pass


class IntegrationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    type: IntegrationType | None = None
    enabled: bool | None = None
    config: dict[str, object] | None = None
    credential_refs: dict[str, str] | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> Self:
        if not self.model_dump(exclude_unset=True):
            raise ValueError("At least one field must be provided")
        if self.config is not None:
            validate_integration_config(self.name or "", self.config)
        return self


class IntegrationRead(IntegrationBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IntegrationTestRead(BaseModel):
    integration_id: UUID
    status: str
    message: str


def validate_integration_config(name: str, config: dict[str, object]) -> None:
    normalized = name.lower()
    url_keys = ("api_url", "url", "base_url")
    if any(label in normalized for label in ("proxmox", "prometheus", "grafana", "tailscale")):
        if not any(isinstance(config.get(key), str) and str(config.get(key)).strip() for key in url_keys):
            raise ValueError("Integration URL is required")

    timeout = config.get("timeout_seconds")
    if timeout is not None:
        if not isinstance(timeout, int) or timeout < 1 or timeout > 120:
            raise ValueError("timeout_seconds must be between 1 and 120")

    verify_ssl = config.get("verify_ssl")
    if verify_ssl is not None and not isinstance(verify_ssl, bool):
        raise ValueError("verify_ssl must be a boolean")
