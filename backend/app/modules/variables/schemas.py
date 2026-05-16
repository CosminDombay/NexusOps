from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VariableCreate(BaseModel):
    key: str = Field(min_length=1, max_length=255)
    value: str | None = None
    description: str = Field(default="", max_length=2000)
    category: str = Field(default="general", min_length=1, max_length=100)
    is_secret: bool = False
    credential_id: UUID | None = None

    @model_validator(mode="after")
    def validate_secret_reference(self) -> Self:
        if self.is_secret and self.credential_id is None:
            raise ValueError("Secret variables must reference a credential")
        if self.is_secret:
            self.value = None
        return self


class VariableRead(BaseModel):
    id: UUID
    key: str
    value: str | None = None
    description: str
    category: str
    is_secret: bool
    credential_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
