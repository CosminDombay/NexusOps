from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.modules.auth.models import UserRole


def validate_session_timeout(value: int | None) -> int | None:
    if value is None:
        return None
    if value == 0:
        return value
    if value < 15 or value > 43200:
        raise ValueError("Session inactivity timeout must be 0, or between 15 and 43200 minutes")
    return value


class UserRead(BaseModel):
    id: UUID
    email: str
    username: str
    role: UserRole
    is_active: bool
    is_superuser: bool
    session_inactivity_timeout_minutes: int | None = None
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    username_or_email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)

    @field_validator("username_or_email")
    @classmethod
    def normalize_login(cls, value: str) -> str:
        stripped = value.strip().lower()
        if not stripped:
            raise ValueError("Username or email is required")
        return stripped


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserRead


class AccessTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=255)
    role: UserRole = UserRole.VIEWER
    is_active: bool = True
    is_superuser: bool = False
    session_inactivity_timeout_minutes: int | None = None

    @field_validator("email", "username")
    @classmethod
    def normalize_identity(cls, value: str) -> str:
        stripped = value.strip().lower()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @field_validator("session_inactivity_timeout_minutes")
    @classmethod
    def validate_session_timeout_value(cls, value: int | None) -> int | None:
        return validate_session_timeout(value)


class UserUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=255)
    username: str | None = Field(default=None, min_length=1, max_length=100)
    role: UserRole | None = None
    is_active: bool | None = None
    is_superuser: bool | None = None
    session_inactivity_timeout_minutes: int | None = None

    @field_validator("email", "username")
    @classmethod
    def normalize_optional_identity(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip().lower()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @field_validator("session_inactivity_timeout_minutes")
    @classmethod
    def validate_optional_session_timeout_value(cls, value: int | None) -> int | None:
        return validate_session_timeout(value)


class UserPasswordReset(BaseModel):
    password: str = Field(min_length=8, max_length=255)
