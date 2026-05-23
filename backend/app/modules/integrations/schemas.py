from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.modules.integrations.models import IntegrationProviderType, IntegrationState, IntegrationType


class IntegrationFields(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: IntegrationType
    provider_type: IntegrationProviderType = IntegrationProviderType.CUSTOM
    enabled: bool = True
    state: IntegrationState = IntegrationState.DISCONNECTED
    config: dict[str, object] = Field(default_factory=dict)
    credential_refs: dict[str, str] = Field(default_factory=dict)
    last_successful_sync: datetime | None = None
    last_error: str | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped


class IntegrationBase(IntegrationFields):
    @model_validator(mode="after")
    def validate_known_config(self) -> Self:
        validate_integration_config(self.provider_type, self.config)
        return self


class IntegrationCreate(IntegrationBase):
    state: IntegrationState | None = None
    last_successful_sync: datetime | None = None
    last_error: str | None = None


class IntegrationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    type: IntegrationType | None = None
    provider_type: IntegrationProviderType | None = None
    enabled: bool | None = None
    state: IntegrationState | None = None
    config: dict[str, object] | None = None
    credential_refs: dict[str, str] | None = None
    last_successful_sync: datetime | None = None
    last_error: str | None = None

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
            validate_integration_config(self.provider_type or IntegrationProviderType.CUSTOM, self.config)
        return self


class IntegrationRead(IntegrationFields):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IntegrationTestRead(BaseModel):
    integration_id: UUID
    status: str
    message: str


def validate_integration_config(provider_type: IntegrationProviderType, config: dict[str, object]) -> None:
    url_keys = ("api_url", "url", "base_url")
    if provider_type != IntegrationProviderType.CUSTOM:
        if not any(isinstance(config.get(key), str) and str(config.get(key)).strip() for key in url_keys):
            raise ValueError("Integration URL is required")

    timeout = config.get("timeout_seconds")
    if timeout is not None:
        if not isinstance(timeout, int) or timeout < 1 or timeout > 120:
            raise ValueError("timeout_seconds must be between 1 and 120")

    verify_ssl = config.get("verify_ssl")
    if verify_ssl is not None and not isinstance(verify_ssl, bool):
        raise ValueError("verify_ssl must be a boolean")
