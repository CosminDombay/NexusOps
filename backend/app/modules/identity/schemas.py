import re
from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.modules.identity.models import IdentityExecutionStatus
from backend.app.modules.jobs.schemas import BulkExecutionHostResult

USERNAME_PATTERN = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
GROUP_PATTERN = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
MODE_PATTERN = re.compile(r"^[0-7]{3,4}$")
PUBLIC_KEY_PATTERN = re.compile(r"^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp(256|384|521))\s+[A-Za-z0-9+/=]+(?:\s+.*)?$")
ALLOWED_SHELLS = {
    "/bin/bash",
    "/bin/sh",
    "/usr/bin/bash",
    "/usr/bin/zsh",
    "/bin/zsh",
    "/bin/rbash",
    "/usr/sbin/nologin",
    "/bin/false",
}


class ReplicationRequest(BaseModel):
    target_server_ids: list[UUID] = Field(min_length=1)


class LinuxUserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    shell: str = "/bin/bash"
    home_directory: str | None = None
    password_credential_ref: str | None = Field(default=None, max_length=255)
    sudo_enabled: bool = False
    sudo_nopasswd: bool = False
    locked: bool = False
    managed: bool = True
    create_home: bool = True
    supplementary_groups: list[str] = Field(default_factory=list)
    target_server_ids: list[UUID] = Field(default_factory=list)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        stripped = value.strip()
        if not USERNAME_PATTERN.match(stripped):
            raise ValueError("Invalid Linux username")
        if stripped == "root":
            raise ValueError("NexusOps cannot manage the root account")
        return stripped

    @field_validator("shell")
    @classmethod
    def validate_shell(cls, value: str) -> str:
        stripped = value.strip()
        if stripped not in ALLOWED_SHELLS:
            raise ValueError("Unsupported shell")
        return stripped

    @field_validator("home_directory")
    @classmethod
    def validate_home(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_absolute_path(value)

    @field_validator("password_credential_ref")
    @classmethod
    def validate_password_credential_ref(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("supplementary_groups")
    @classmethod
    def validate_groups(cls, value: list[str]) -> list[str]:
        normalized = []
        for group in value:
            stripped = group.strip()
            if stripped == "__admin__":
                normalized.append(stripped)
                continue
            if not GROUP_PATTERN.match(stripped):
                raise ValueError("Invalid Linux group name")
            normalized.append(stripped)
        return normalized


class LinuxUserRead(BaseModel):
    id: UUID
    username: str
    shell: str
    home_directory: str
    sudo_enabled: bool
    sudo_nopasswd: bool
    locked: bool
    managed: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LinuxUserUpdate(BaseModel):
    shell: str = "/bin/bash"
    home_directory: str | None = None
    password_credential_ref: str | None = Field(default=None, max_length=255)
    sudo_enabled: bool = False
    sudo_nopasswd: bool = False
    locked: bool = False
    managed: bool = True
    supplementary_groups: list[str] = Field(default_factory=list)
    target_server_ids: list[UUID] = Field(default_factory=list)

    @field_validator("shell")
    @classmethod
    def validate_shell(cls, value: str) -> str:
        stripped = value.strip()
        if stripped not in ALLOWED_SHELLS:
            raise ValueError("Unsupported shell")
        return stripped

    @field_validator("home_directory")
    @classmethod
    def validate_home(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_absolute_path(value)

    @field_validator("password_credential_ref")
    @classmethod
    def validate_password_credential_ref(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("supplementary_groups")
    @classmethod
    def validate_groups(cls, value: list[str]) -> list[str]:
        normalized = []
        for group in value:
            stripped = group.strip()
            if stripped == "__admin__":
                normalized.append(stripped)
                continue
            if not GROUP_PATTERN.match(stripped):
                raise ValueError("Invalid Linux group name")
            normalized.append(stripped)
        return normalized


class LinuxGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    description: str | None = Field(default=None, max_length=2000)
    managed: bool = True
    target_server_ids: list[UUID] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        stripped = value.strip()
        if not GROUP_PATTERN.match(stripped):
            raise ValueError("Invalid Linux group name")
        return stripped


class LinuxGroupRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    managed: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LinuxGroupUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    description: str | None = Field(default=None, max_length=2000)
    managed: bool = True
    target_server_ids: list[UUID] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        stripped = value.strip()
        if not GROUP_PATTERN.match(stripped):
            raise ValueError("Invalid Linux group name")
        return stripped


class GroupMembersRequest(BaseModel):
    usernames: list[str] = Field(min_length=1)
    target_server_ids: list[UUID] = Field(min_length=1)

    @field_validator("usernames")
    @classmethod
    def validate_usernames(cls, value: list[str]) -> list[str]:
        normalized = []
        for username in value:
            stripped = username.strip()
            if not USERNAME_PATTERN.match(stripped):
                raise ValueError("Invalid Linux username")
            normalized.append(stripped)
        return normalized


class SSHKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    public_key: str = Field(min_length=32, max_length=2000)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @field_validator("public_key")
    @classmethod
    def validate_public_key(cls, value: str) -> str:
        stripped = value.strip()
        if not PUBLIC_KEY_PATTERN.match(stripped):
            raise ValueError("Invalid SSH public key")
        return stripped


class SSHKeyRead(BaseModel):
    id: UUID
    name: str
    public_key: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SSHKeyDeployRequest(ReplicationRequest):
    username: str = Field(min_length=1, max_length=32)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        stripped = value.strip()
        if not USERNAME_PATTERN.match(stripped):
            raise ValueError("Invalid Linux username")
        return stripped


class PermissionTemplateCreate(BaseModel):
    path: str = Field(min_length=1, max_length=1000)
    owner: str | None = Field(default=None, max_length=32)
    group: str | None = Field(default=None, max_length=32)
    mode: str | None = Field(default=None, max_length=4)
    recursive: bool = False
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return validate_absolute_path(value)

    @field_validator("owner", "group")
    @classmethod
    def validate_principal(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not USERNAME_PATTERN.match(stripped):
            raise ValueError("Invalid Linux owner/group")
        return stripped

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not MODE_PATTERN.match(stripped):
            raise ValueError("Invalid file mode")
        return stripped

    @model_validator(mode="after")
    def require_action(self) -> Self:
        if not self.owner and not self.group and not self.mode:
            raise ValueError("At least one of owner, group, or mode is required")
        return self


class PermissionTemplateRead(BaseModel):
    id: UUID
    path: str
    owner: str | None
    group: str | None
    mode: str | None
    recursive: bool
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PermissionApplyRequest(PermissionTemplateCreate):
    target_server_ids: list[UUID] = Field(min_length=1)


class PermissionReplicateRequest(ReplicationRequest):
    pass


class IdentityExecutionRead(BaseModel):
    id: UUID
    operation_type: str
    target_server_id: UUID
    job_id: UUID | None
    status: IdentityExecutionStatus
    stdout: str | None
    stderr: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IdentityReplicationRead(BaseModel):
    operation_type: str
    success_count: int
    failure_count: int
    results: list[BulkExecutionHostResult]


class AccessProfileRead(BaseModel):
    id: str
    name: str
    description: str
    shell: str
    sudo_enabled: bool
    sudo_nopasswd: bool
    supplementary_groups: list[str]
    permission_presets: list[str] = Field(default_factory=list)
    advanced: bool = False


class GroupPresetRead(BaseModel):
    id: str
    name: str
    group: str
    description: str
    recommended_for: str
    distro_families: list[str]


class PermissionPresetRead(BaseModel):
    id: str
    name: str
    mode: str
    description: str
    owner: str | None = None
    group: str | None = None
    recursive: bool = False


class DiscoveredGroupRead(BaseModel):
    name: str
    hosts: list[str]
    gid: int | None = None
    members: list[str] = Field(default_factory=list)


class DiscoveredUserRead(BaseModel):
    username: str
    hosts: list[str]
    uid: int | None = None
    gid: int | None = None
    home_directory: str | None = None
    shell: str | None = None


class GroupDiscoveryRead(BaseModel):
    groups: list[DiscoveredGroupRead]


class UserDiscoveryRead(BaseModel):
    users: list[DiscoveredUserRead]


class UserGroupMembershipHostRead(BaseModel):
    target_server_id: UUID
    target_hostname: str | None = None
    groups: list[str] = Field(default_factory=list)
    error: str | None = None


class UserGroupMembershipRead(BaseModel):
    username: str
    hosts: list[UserGroupMembershipHostRead]


class GroupMemberHostRead(BaseModel):
    target_server_id: UUID
    target_hostname: str | None = None
    members: list[str] = Field(default_factory=list)
    primary_members: list[str] = Field(default_factory=list)
    supplementary_members: list[str] = Field(default_factory=list)
    error: str | None = None


class GroupMembershipRead(BaseModel):
    group: str
    hosts: list[GroupMemberHostRead]


class IdentityMutationRead(BaseModel):
    item: LinuxUserRead | LinuxGroupRead | SSHKeyRead | PermissionTemplateRead
    replication: IdentityReplicationRead | None = None


def validate_absolute_path(value: str) -> str:
    stripped = value.strip()
    if not stripped.startswith("/"):
        raise ValueError("Path must be absolute")
    if any(token in stripped for token in [";", "&&", "||", "`", "$(", "\n", "\r"]):
        raise ValueError("Path contains unsafe shell metacharacters")
    return stripped
