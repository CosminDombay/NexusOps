# Profiles And Packages Review

Generated from the current NexusOps workspace for focused code review.

## backend/app/modules/profiles/models.py

``python
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class StandardizationProfile(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "standardization_profiles"

    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(500))
    users: Mapped[list[dict]] = mapped_column(JSON, default=list)
    groups: Mapped[list[dict]] = mapped_column(JSON, default=list)


class InfrastructureProfileRecord(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "infrastructure_profiles"
    __table_args__ = (UniqueConstraint("slug", name="uq_infrastructure_profiles_slug"),)

    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    steps: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    variables: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_modified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    base_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_template_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

````

## backend/app/modules/profiles/schemas.py

``python
from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.app.modules.jobs.schemas import JobRead
from backend.app.modules.packages.schemas import VariableDefinitionRead


class ProfileStepRead(BaseModel):
    id: str
    name: str
    kind: Literal["action", "package", "command", "deployment", "script"]
    reference_id: str
    command: str | None = None
    type: Literal["action", "package", "deployment", "script"] | None = None
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
    kind: Literal["action", "package", "command", "deployment", "script"] | None = None
    type: Literal["action", "package", "deployment", "script"] | None = None
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
        if self.kind not in {"action", "package", "deployment"}:
            raise ValueError("Step type is required")
        if not self.reference_id:
            raise ValueError("Package, action, and deployment steps require a target")
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

````

## backend/app/modules/profiles/repository.py

``python
from backend.app.common.repository import BaseRepository
from backend.app.modules.profiles.models import InfrastructureProfileRecord, StandardizationProfile

from sqlalchemy import delete, select
from uuid import UUID


class StandardizationProfileRepository(BaseRepository[StandardizationProfile]):
    pass


class InfrastructureProfileRepository(BaseRepository[InfrastructureProfileRecord]):
    async def create(self, profile: InfrastructureProfileRecord) -> InfrastructureProfileRecord:
        self.session.add(profile)
        await self.session.flush()
        await self.session.refresh(profile)
        return profile

    async def list(self) -> list[InfrastructureProfileRecord]:
        result = await self.session.execute(
            select(InfrastructureProfileRecord).order_by(InfrastructureProfileRecord.name.asc())
        )
        return list(result.scalars().all())

    async def get_by_slug(self, slug: str) -> InfrastructureProfileRecord | None:
        result = await self.session.execute(
            select(InfrastructureProfileRecord).where(InfrastructureProfileRecord.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, profile_id: UUID) -> InfrastructureProfileRecord | None:
        result = await self.session.execute(
            select(InfrastructureProfileRecord).where(InfrastructureProfileRecord.id == profile_id)
        )
        return result.scalar_one_or_none()

    async def delete(self, profile: InfrastructureProfileRecord) -> None:
        await self.session.execute(
            delete(InfrastructureProfileRecord).where(InfrastructureProfileRecord.id == profile.id)
        )

````

## backend/app/modules/profiles/service.py

``python
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from backend.app.common.variables import VariableResolutionError, VariableResolutionService
from backend.app.modules.deployments.service import DockerComposeDeploymentService
from backend.app.modules.jobs.actions import get_action
from backend.app.modules.jobs.models import JobStatus
from backend.app.modules.jobs.schemas import JobExecuteRequest
from backend.app.modules.jobs.service import JobService
from backend.app.modules.orchestration.semantics import job_failure_states, job_success_states
from backend.app.modules.orchestration.utils import success_failure_counts, summarize_statuses
from backend.app.modules.packages.definitions import get_package_definition
from backend.app.modules.packages.repository import PackageDefinitionRepository
from backend.app.modules.packages.service import PackageAutomationService
from backend.app.modules.profiles.definitions import InfrastructureProfile, get_profile, list_profiles
from backend.app.modules.profiles.models import InfrastructureProfileRecord
from backend.app.modules.profiles.repository import InfrastructureProfileRepository
from backend.app.modules.profiles.schemas import (
    InfrastructureProfileCreate,
    InfrastructureProfileRead,
    InfrastructureProfileUpdate,
    ProfileApplyRead,
    ProfileBulkApplyRead,
    ProfileBulkApplyRequest,
    ProfileBulkHostResult,
    ProfileApplyRequest,
    ProfileCloneRequest,
)
from backend.app.modules.workflows.models import WorkflowTriggerSource, WorkflowType
from backend.app.modules.workflows.schemas import WorkflowCreate, WorkflowRunRead, WorkflowStepCreate, WorkflowStepRead
from backend.app.modules.workflows.service import WorkflowService


class ProfileNotFoundError(Exception):
    """Raised when a profile template cannot be found."""


class ProfileStepResolutionError(Exception):
    """Raised when a profile step references an unknown action/package."""


class ProfileConflictError(Exception):
    """Raised when a profile slug already exists."""


class BuiltinProfileError(Exception):
    """Raised when trying to mutate a built-in profile."""


SYSTEM_TEMPLATE_VERSION = "2026.05.16"


class ProfileService:
    """Application service for reusable infrastructure profile orchestration."""

    def __init__(
        self,
        *,
        job_service: JobService,
        repository: InfrastructureProfileRepository | None = None,
        package_repository: PackageDefinitionRepository | None = None,
        deployment_service: DockerComposeDeploymentService | None = None,
        workflow_service: WorkflowService | None = None,
    ) -> None:
        self.job_service = job_service
        self.repository = repository
        self.package_repository = package_repository
        self.deployment_service = deployment_service
        self.workflow_service = workflow_service
        self.variable_service = VariableResolutionService()

    async def list_profiles(self) -> list[InfrastructureProfileRead]:
        profiles = [self._builtin_to_read(profile) for profile in list_profiles()]
        if self.repository is None:
            return profiles

        custom_profiles = [self._record_to_read(record) for record in await self.repository.list()]
        custom_ids = {profile.id for profile in custom_profiles}
        return [profile for profile in profiles if profile.id not in custom_ids] + custom_profiles

    async def get_profile(self, profile_id: str) -> InfrastructureProfileRead:
        if self.repository is not None:
            record = await self.repository.get_by_slug(profile_id)
            if record is not None:
                return self._record_to_read(record)

        profile = get_profile(profile_id)
        if profile is None:
            raise ProfileNotFoundError("Profile not found")
        return self._builtin_to_read(profile)

    async def create_profile(self, payload: InfrastructureProfileCreate) -> InfrastructureProfileRead:
        if self.repository is None:
            raise RuntimeError("Profile repository is required")

        if get_profile(payload.id) or await self.repository.get_by_slug(payload.id):
            raise ProfileConflictError("Profile already exists")

        record = InfrastructureProfileRecord(
            slug=payload.id,
            name=payload.name,
            category=payload.category,
            description=payload.description,
            tags=payload.tags,
            steps=[self._normalize_step(step.model_dump()) for step in payload.steps],
            variables=[variable.model_dump() for variable in payload.variables],
            is_builtin=False,
        )
        try:
            record = await self.repository.create(record)
            await self.repository.session.commit()
        except IntegrityError as exc:
            await self.repository.session.rollback()
            raise ProfileConflictError("Profile already exists") from exc
        return self._record_to_read(record)

    async def update_profile(
        self,
        profile_id: str,
        payload: InfrastructureProfileUpdate,
    ) -> InfrastructureProfileRead:
        if self.repository is None:
            raise RuntimeError("Profile repository is required")

        record = await self.repository.get_by_slug(profile_id)
        builtin = get_profile(profile_id)
        if record is None and builtin is not None:
            record = await self._create_builtin_override(builtin)
        if record is None:
            raise ProfileNotFoundError("Profile not found")

        update_data = payload.model_dump(exclude_unset=True)
        if "steps" in update_data and update_data["steps"] is not None:
            update_data["steps"] = [
                self._normalize_step(step.model_dump() if hasattr(step, "model_dump") else step)
                for step in payload.steps or []
            ]
        if "variables" in update_data and update_data["variables"] is not None:
            update_data["variables"] = [
                variable.model_dump() if hasattr(variable, "model_dump") else variable
                for variable in payload.variables or []
            ]

        for key, value in update_data.items():
            setattr(record, key, value)
        record.is_modified = True
        record.modified_at = datetime.now(UTC)

        await self.repository.session.commit()
        await self.repository.session.refresh(record)
        return self._record_to_read(record)

    async def delete_profile(self, profile_id: str) -> None:
        if self.repository is None:
            raise RuntimeError("Profile repository is required")

        if get_profile(profile_id):
            raise BuiltinProfileError("Built-in profiles cannot be deleted")

        record = await self.repository.get_by_slug(profile_id)
        if record is None:
            raise ProfileNotFoundError("Profile not found")

        await self.repository.delete(record)
        await self.repository.session.commit()

    async def clone_profile(self, profile_id: str, payload: ProfileCloneRequest) -> InfrastructureProfileRead:
        if self.repository is None:
            raise RuntimeError("Profile repository is required")
        if get_profile(payload.id) or await self.repository.get_by_slug(payload.id):
            raise ProfileConflictError("Profile already exists")
        source = await self.get_profile(profile_id)
        record = InfrastructureProfileRecord(
            slug=payload.id,
            name=payload.name or f"{source.name} Copy",
            category=source.category,
            description=source.description,
            tags=[*source.tags, "cloned"],
            steps=[self._normalize_step(step.model_dump()) for step in source.steps],
            variables=[variable.model_dump() for variable in source.variables],
            is_builtin=False,
            is_modified=False,
            base_version=source.base_version,
            source_template_id=source.id,
        )
        try:
            record = await self.repository.create(record)
            await self.repository.session.commit()
        except IntegrityError as exc:
            await self.repository.session.rollback()
            raise ProfileConflictError("Profile already exists") from exc
        return self._record_to_read(record)

    async def reset_profile(self, profile_id: str) -> InfrastructureProfileRead:
        if self.repository is None:
            raise RuntimeError("Profile repository is required")
        if get_profile(profile_id) is None:
            raise BuiltinProfileError("Only built-in profiles can be reset")
        record = await self.repository.get_by_slug(profile_id)
        if record is not None:
            await self.repository.delete(record)
            await self.repository.session.commit()
        return await self.get_profile(profile_id)

    async def apply_profile(self, profile_id: str, payload: ProfileApplyRequest) -> ProfileApplyRead:
        profile = await self.get_profile(profile_id)

        jobs = []
        status = "success"
        workflow = await self._start_profile_workflow(profile, payload)
        try:
            step_order = 0
            for step in profile.steps:
                if getattr(step, "enabled", True) is False:
                    continue
                step_order += 1
                workflow_step = await self._start_profile_workflow_step(
                    workflow,
                    profile,
                    step,
                    payload,
                    step_order,
                )
                try:
                    step_jobs = await self._execute_profile_step(profile, step, payload)
                    jobs.extend(step_jobs)
                    await self._finish_profile_workflow_step(
                        workflow_step,
                        profile,
                        step,
                        step_jobs,
                    )
                    if self._profile_step_failed(step_jobs) and payload.stop_on_failure:
                        status = "failed"
                        break
                except Exception as exc:
                    await self._fail_profile_workflow_step(workflow_step, exc)
                    raise

            job_summary = summarize_statuses(
                jobs,
                success_states=job_success_states(),
                failure_states=job_failure_states(),
            )
            if job_summary.has_failures and status != "failed":
                status = "completed_with_failures"
            await self._finish_profile_workflow(workflow, profile, status, jobs)
        except Exception as exc:
            await self._fail_profile_workflow(workflow, profile, exc, jobs)
            raise

        return ProfileApplyRead(
            profile_id=profile.id,
            target_server_id=payload.target_server_id,
            status=status,
            jobs=jobs,
            message=f"Profile {profile.name} executed {len(jobs)} step(s).",
        )

    async def apply_profile_bulk(self, payload: ProfileBulkApplyRequest) -> ProfileBulkApplyRead:
        results: list[ProfileBulkHostResult] = []
        for target_server_id in payload.target_server_ids:
            server = await self.job_service.server_repository.get_by_id(target_server_id)
            try:
                result = await self.apply_profile(
                    payload.profile_id,
                    ProfileApplyRequest(
                        target_server_id=target_server_id,
                        stop_on_failure=payload.stop_on_failure,
                        variables=payload.variables,
                        credential_refs=payload.credential_refs,
                    ),
                )
                results.append(
                    ProfileBulkHostResult(
                        target_server_id=target_server_id,
                        target_hostname=result.jobs[0].target_hostname if result.jobs else None,
                        success=result.status == "success",
                        result=result,
                        error=None if result.status == "success" else result.status,
                    )
                )
            except Exception as exc:
                results.append(
                    ProfileBulkHostResult(
                        target_server_id=target_server_id,
                        target_hostname=server.hostname if server else None,
                        success=False,
                        error=str(exc),
                    )
                )

        success_count, failure_count = success_failure_counts(results)
        return ProfileBulkApplyRead(
            profile_id=payload.profile_id,
            success_count=success_count,
            failure_count=failure_count,
            results=results,
        )

    async def _execute_profile_step(
        self,
        profile: InfrastructureProfileRead,
        step,
        payload: ProfileApplyRequest,
    ):
        if step.kind == "deployment":
            if self.deployment_service is None:
                raise ProfileStepResolutionError("Deployment service is required for deployment profile steps")
            try:
                deployment_id = UUID(step.reference_id)
            except ValueError as exc:
                raise ProfileStepResolutionError(
                    f"Deployment step requires a deployment UUID: {step.reference_id}"
                ) from exc
            deployment_result = await self.deployment_service.deploy_for_target(
                deployment_id,
                payload.target_server_id,
            )
            return deployment_result.jobs or ([deployment_result.job] if deployment_result.job else [])

        credential_ref = getattr(step, "credential_ref", None)
        command, redacted_command = await self._resolve_step_commands(
            step.kind,
            step.reference_id,
            variables=payload.variables,
            credential_refs=payload.credential_refs,
            command=step.command,
            profile_variables=[variable.model_dump() for variable in profile.variables],
        )
        job = await self.job_service.execute(
            JobExecuteRequest(
                target_server_id=payload.target_server_id,
                operation_type=f"profile:{profile.id}:{step.id}",
                command=command,
                redacted_command=redacted_command,
                credential_ref=credential_ref,
            )
        )
        return [job]

    async def _start_profile_workflow(
        self,
        profile: InfrastructureProfileRead,
        payload: ProfileApplyRequest,
    ) -> WorkflowRunRead | None:
        if self.workflow_service is None:
            return None
        workflow = await self.workflow_service.create_workflow(
            WorkflowCreate(
                workflow_type=WorkflowType.PROFILE_EXECUTION,
                trigger_source=WorkflowTriggerSource.MANUAL,
                target_server_id=payload.target_server_id,
                context_json={
                    "profile_id": profile.id,
                    "profile_name": profile.name,
                    "stop_on_failure": payload.stop_on_failure,
                    "variable_names": sorted(payload.variables),
                    "credential_ref_names": sorted(payload.credential_refs),
                },
            )
        )
        workflow = await self.workflow_service.mark_queued(workflow.id)
        return await self.workflow_service.start_workflow(workflow.id)

    async def _start_profile_workflow_step(
        self,
        workflow: WorkflowRunRead | None,
        profile: InfrastructureProfileRead,
        step,
        payload: ProfileApplyRequest,
        step_order: int,
    ) -> WorkflowStepRead | None:
        if workflow is None or self.workflow_service is None:
            return None
        workflow_step = await self.workflow_service.add_step(
            workflow.id,
            WorkflowStepCreate(
                step_order=step_order,
                step_type=f"profile_{step.kind}",
                name=step.name,
                metadata_json={
                    "profile_id": profile.id,
                    "profile_step_id": step.id,
                    "profile_step_kind": step.kind,
                    "reference_id": step.reference_id,
                    "target_server_id": str(payload.target_server_id),
                    "operation_type": f"profile:{profile.id}:{step.id}",
                },
            ),
        )
        return await self.workflow_service.start_step(workflow_step.id)

    async def _finish_profile_workflow_step(
        self,
        workflow_step: WorkflowStepRead | None,
        profile: InfrastructureProfileRead,
        step,
        jobs,
    ) -> None:
        if workflow_step is None or self.workflow_service is None:
            return
        job_ids = [str(job.id) for job in jobs]
        metadata = {
            "job_ids": job_ids,
            "job_statuses": [str(job.status) for job in jobs],
            "profile_id": profile.id,
            "profile_step_id": step.id,
            "profile_step_kind": step.kind,
        }
        if self._profile_step_failed(jobs):
            await self.workflow_service.fail_step(
                workflow_step.id,
                error_output=self._profile_step_error(jobs),
                log_output=f"Profile step {step.name} completed with failure.",
                metadata_json=metadata,
            )
            return
        await self.workflow_service.complete_step(
            workflow_step.id,
            log_output=f"Profile step {step.name} completed.",
            metadata_json=metadata,
        )

    async def _fail_profile_workflow_step(
        self,
        workflow_step: WorkflowStepRead | None,
        exc: Exception,
    ) -> None:
        if workflow_step is None or self.workflow_service is None:
            return
        await self.workflow_service.fail_step(workflow_step.id, error_output=str(exc))

    async def _finish_profile_workflow(
        self,
        workflow: WorkflowRunRead | None,
        profile: InfrastructureProfileRead,
        status: str,
        jobs,
    ) -> None:
        if workflow is None or self.workflow_service is None:
            return
        summary = self._profile_workflow_summary(profile, status, jobs)
        if status == "success":
            await self.workflow_service.complete_workflow(workflow.id, result_summary=summary)
            return
        await self.workflow_service.fail_workflow(
            workflow.id,
            error_message=status,
            result_summary=summary,
        )

    async def _fail_profile_workflow(
        self,
        workflow: WorkflowRunRead | None,
        profile: InfrastructureProfileRead,
        exc: Exception,
        jobs,
    ) -> None:
        if workflow is None or self.workflow_service is None:
            return
        await self.workflow_service.fail_workflow(
            workflow.id,
            error_message=str(exc),
            result_summary=self._profile_workflow_summary(profile, "failed", jobs),
        )

    @staticmethod
    def _profile_step_failed(jobs) -> bool:
        return any(job.status in job_failure_states() for job in jobs)

    @staticmethod
    def _profile_step_error(jobs) -> str:
        errors = [job.stderr for job in jobs if job.stderr]
        return "\n".join(errors) if errors else "Profile step failed"

    @staticmethod
    def _profile_workflow_summary(profile: InfrastructureProfileRead, status: str, jobs) -> dict:
        return {
            "profile_id": profile.id,
            "profile_name": profile.name,
            "status": status,
            "job_ids": [str(job.id) for job in jobs],
            "job_count": len(jobs),
            "failed_job_count": sum(
                1 for job in jobs if job.status in job_failure_states()
            ),
        }

    async def _resolve_step_command(
        self,
        kind: str,
        reference_id: str,
        *,
        variables: dict[str, str],
        profile_variables: list[dict],
        command: str | None = None,
    ) -> str:
        if kind == "command":
            return self.variable_service.resolve_text(
                command or "",
                definitions=profile_variables,
                variables=variables,
            )

        if kind in {"deployment", "script"}:
            raise ProfileStepResolutionError(f"Unsupported profile step kind: {kind}")

        if kind == "action":
            action = get_action(reference_id)
            if action is None and self.job_service.action_repository is not None:
                action = await self.job_service.action_repository.get_by_slug(reference_id)
            if action is None:
                raise ProfileStepResolutionError(f"Unknown action reference: {reference_id}")
            return self.variable_service.resolve_text(
                action.command,
                definitions=profile_variables,
                variables=variables,
            )

        if kind == "package":
            package_read = None
            if self.package_repository is not None:
                package_service = PackageAutomationService(repository=self.package_repository)
                try:
                    package_read = await package_service.get_definition(reference_id)
                except Exception:
                    package_read = None
            if package_read is None:
                package = get_package_definition(reference_id)
                if package is None:
                    raise ProfileStepResolutionError(f"Unknown package reference: {reference_id}")
                definitions = [*profile_variables, *package.variables]
                install = self.variable_service.resolve_text(package.install_command, definitions=definitions, variables=variables)
                validation = self.variable_service.resolve_text(package.validation_command, definitions=definitions, variables=variables)
                return f"{install} && {validation}"
            definitions = [*profile_variables, *[variable.model_dump() for variable in package_read.variables]]
            install = self.variable_service.resolve_text(package_read.install_command, definitions=definitions, variables=variables)
            validation = self.variable_service.resolve_text(package_read.validation_command, definitions=definitions, variables=variables)
            return f"{install} && {validation}"

        raise ProfileStepResolutionError(f"Unsupported profile step kind: {kind}")

    async def _resolve_step_commands(
        self,
        kind: str,
        reference_id: str,
        *,
        variables: dict[str, str],
        credential_refs: dict[str, str],
        profile_variables: list[dict],
        command: str | None = None,
    ) -> tuple[str, str]:
        if kind == "command":
            return await self._resolve_text_pair(command or "", profile_variables, variables, credential_refs)

        if kind == "action":
            action = get_action(reference_id)
            if action is None and self.job_service.action_repository is not None:
                action = await self.job_service.action_repository.get_by_slug(reference_id)
            if action is None:
                raise ProfileStepResolutionError(f"Unknown action reference: {reference_id}")
            return await self._resolve_text_pair(action.command, profile_variables, variables, credential_refs)

        if kind == "package":
            package_read = None
            if self.package_repository is not None:
                package_service = PackageAutomationService(
                    repository=self.package_repository,
                    credential_service=self.job_service.credential_service,
                )
                try:
                    package_read = await package_service.get_definition(reference_id)
                except Exception:
                    package_read = None
            if package_read is None:
                package = get_package_definition(reference_id)
                if package is None:
                    raise ProfileStepResolutionError(f"Unknown package reference: {reference_id}")
                definitions = [*profile_variables, *package.variables]
                install, redacted_install = await self._resolve_text_pair(
                    package.install_command,
                    definitions,
                    variables,
                    credential_refs,
                )
                validation, redacted_validation = await self._resolve_text_pair(
                    package.validation_command,
                    definitions,
                    variables,
                    credential_refs,
                )
                return f"{install} && {validation}", f"{redacted_install} && {redacted_validation}"

            definitions = [*profile_variables, *[variable.model_dump() for variable in package_read.variables]]
            install, redacted_install = await self._resolve_text_pair(
                package_read.install_command,
                definitions,
                variables,
                credential_refs,
            )
            validation, redacted_validation = await self._resolve_text_pair(
                package_read.validation_command,
                definitions,
                variables,
                credential_refs,
            )
            return f"{install} && {validation}", f"{redacted_install} && {redacted_validation}"

        raise ProfileStepResolutionError(f"Unsupported profile step kind: {kind}")

    async def _resolve_text_pair(
        self,
        text: str,
        definitions: list[dict],
        variables: dict[str, str],
        credential_refs: dict[str, str],
    ) -> tuple[str, str]:
        secret_values = await self._resolve_secret_variables(definitions, credential_refs)
        safe_variables = self._without_sensitive_plaintext(definitions, variables, credential_refs)
        runtime_variables = {**safe_variables, **secret_values}
        redacted_variables = {**safe_variables, **{name: "********" for name in secret_values}}
        return (
            self.variable_service.resolve_text(text, definitions=definitions, variables=runtime_variables),
            self.variable_service.resolve_text(text, definitions=definitions, variables=redacted_variables),
        )

    async def _resolve_secret_variables(
        self,
        definitions: list[dict],
        credential_refs: dict[str, str],
    ) -> dict[str, str]:
        secret_values: dict[str, str] = {}
        sensitive_names = [str(item["name"]) for item in definitions if item.get("name") and item.get("sensitive")]
        for name in sensitive_names:
            credential_ref = credential_refs.get(name)
            if not credential_ref:
                definition = next(item for item in definitions if item.get("name") == name)
                if definition.get("required"):
                    raise VariableResolutionError(f"Sensitive variable {name} requires a credential reference")
                continue
            if self.job_service.credential_service is None:
                raise VariableResolutionError("Credential service is required for sensitive profile variables")
            credential = await self.job_service.credential_service.resolve_credential(credential_ref)
            secret = credential.secret or credential.private_key
            if not secret:
                raise VariableResolutionError(f"Credential reference for {name} has no usable secret value")
            secret_values[name] = secret
        return secret_values

    @staticmethod
    def _without_sensitive_plaintext(
        definitions: list[dict],
        variables: dict[str, str],
        credential_refs: dict[str, str],
    ) -> dict[str, str]:
        sensitive_names = {str(item["name"]) for item in definitions if item.get("name") and item.get("sensitive")}
        unsafe = sorted(name for name in sensitive_names if variables.get(name) and not credential_refs.get(name))
        if unsafe:
            raise VariableResolutionError(
                "Sensitive variable(s) must use credential references: " + ", ".join(unsafe)
            )
        return {name: value for name, value in variables.items() if name not in sensitive_names}

    @staticmethod
    def _builtin_to_read(profile: InfrastructureProfile) -> InfrastructureProfileRead:
        return InfrastructureProfileRead(
            id=profile.id,
            name=profile.name,
            category=profile.category,
            description=profile.description,
            tags=profile.tags,
            steps=[ProfileService._normalize_step(step.__dict__) for step in profile.steps],
            variables=profile.variables,
            is_builtin=True,
            is_modified=False,
            base_version=SYSTEM_TEMPLATE_VERSION,
        )

    @staticmethod
    def _record_to_read(record: InfrastructureProfileRecord) -> InfrastructureProfileRead:
        return InfrastructureProfileRead(
            id=record.slug,
            name=record.name,
            category=record.category,
            description=record.description,
            tags=record.tags,
            steps=[ProfileService._normalize_step(step) for step in record.steps],
            variables=record.variables,
            is_builtin=record.is_builtin,
            is_modified=record.is_modified,
            base_version=record.base_version,
            source_template_id=record.source_template_id,
            modified_at=record.modified_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    async def _create_builtin_override(self, profile: InfrastructureProfile) -> InfrastructureProfileRecord:
        assert self.repository is not None
        record = InfrastructureProfileRecord(
            slug=profile.id,
            name=profile.name,
            category=profile.category,
            description=profile.description,
            tags=profile.tags,
            steps=[ProfileService._normalize_step(step.__dict__) for step in profile.steps],
            variables=profile.variables,
            is_builtin=True,
            is_modified=False,
            base_version=SYSTEM_TEMPLATE_VERSION,
            source_template_id=profile.id,
        )
        record = await self.repository.create(record)
        await self.repository.session.flush()
        return record

    @staticmethod
    def _normalize_step(step: dict) -> dict:
        kind = step.get("kind") or ("command" if step.get("type") == "script" else step.get("type"))
        reference_id = step.get("reference_id") or step.get("target") or step.get("id") or ""
        step_type = "script" if kind == "command" else kind
        return {
            **step,
            "id": step.get("id") or f"{kind}-{reference_id}",
            "name": step.get("name") or reference_id,
            "kind": kind,
            "reference_id": reference_id,
            "type": step.get("type") or step_type,
            "target": step.get("target") or reference_id,
            "enabled": step.get("enabled", True),
            "credential_ref": step.get("credential_ref"),
        }

````

## backend/app/modules/profiles/router.py

``python
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.ssh import ParamikoSshAdapter
from backend.app.db.session import AsyncSessionLocal, get_db_session
from backend.app.modules.audit.repository import AuditEventRepository
from backend.app.modules.audit.service import AuditService
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.service import CredentialNotFoundError, CredentialService
from backend.app.modules.deployments.repository import (
    DeploymentRepository,
    DeploymentRevisionRepository,
    DeploymentTargetRepository,
)
from backend.app.modules.deployments.service import DeploymentNotFoundError, DeploymentValidationError, DockerComposeDeploymentService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.jobs.repository import CustomOperationalActionRepository, JobRepository
from backend.app.modules.jobs.service import JobService, JobTargetNotFoundError, JobTargetNotManagedError
from backend.app.modules.packages.repository import PackageDefinitionRepository
from backend.app.modules.profiles.repository import InfrastructureProfileRepository
from backend.app.modules.profiles.schemas import (
    InfrastructureProfileCreate,
    InfrastructureProfileRead,
    InfrastructureProfileUpdate,
    ProfileCloneRequest,
    ProfileApplyRead,
    ProfileBulkApplyRead,
    ProfileBulkApplyRequest,
    ProfileApplyRequest,
)
from backend.app.common.variables import VariableResolutionError
from backend.app.modules.profiles.service import (
    BuiltinProfileError,
    ProfileConflictError,
    ProfileNotFoundError,
    ProfileService,
    ProfileStepResolutionError,
)
from backend.app.modules.workflows.repository import WorkflowRunRepository, WorkflowStepRepository
from backend.app.modules.workflows.service import WorkflowService

router = APIRouter()


async def get_profile_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProfileService:
    server_repository = ServerRepository(session)
    credential_service = CredentialService(repository=CredentialRepository(session))
    job_service = JobService(
        job_repository=JobRepository(session),
        server_repository=server_repository,
        ssh_adapter=ParamikoSshAdapter(),
        action_repository=CustomOperationalActionRepository(session),
        credential_service=credential_service,
        audit_service=AuditService(AuditEventRepository(session)),
        session_factory=AsyncSessionLocal,
    )
    return ProfileService(
        job_service=job_service,
        repository=InfrastructureProfileRepository(session),
        package_repository=PackageDefinitionRepository(session),
        deployment_service=DockerComposeDeploymentService(
            repository=DeploymentRepository(session),
            target_repository=DeploymentTargetRepository(session),
            revision_repository=DeploymentRevisionRepository(session),
            server_repository=server_repository,
            job_service=job_service,
            credential_service=credential_service,
        ),
        workflow_service=WorkflowService(
            workflow_repository=WorkflowRunRepository(session),
            step_repository=WorkflowStepRepository(session),
            server_repository=server_repository,
            audit_service=AuditService(AuditEventRepository(session)),
        ),
    )


@router.get("", response_model=list[InfrastructureProfileRead])
async def list_profiles(
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> list[InfrastructureProfileRead]:
    return await service.list_profiles()


@router.post("/apply/bulk", response_model=ProfileBulkApplyRead, status_code=status.HTTP_201_CREATED)
async def apply_profile_bulk(
    payload: ProfileBulkApplyRequest,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileBulkApplyRead:
    return await service.apply_profile_bulk(payload)


@router.post("", response_model=InfrastructureProfileRead, status_code=status.HTTP_201_CREATED)
async def create_profile(
    payload: InfrastructureProfileCreate,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> InfrastructureProfileRead:
    try:
        return await service.create_profile(payload)
    except ProfileConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/{profile_id}", response_model=InfrastructureProfileRead)
async def get_profile(
    profile_id: str,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> InfrastructureProfileRead:
    try:
        return await service.get_profile(profile_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/{profile_id}", response_model=InfrastructureProfileRead)
async def update_profile(
    profile_id: str,
    payload: InfrastructureProfileUpdate,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> InfrastructureProfileRead:
    try:
        return await service.update_profile(profile_id, payload)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except BuiltinProfileError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{profile_id}/clone", response_model=InfrastructureProfileRead, status_code=status.HTTP_201_CREATED)
async def clone_profile(
    profile_id: str,
    payload: ProfileCloneRequest,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> InfrastructureProfileRead:
    try:
        return await service.clone_profile(profile_id, payload)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProfileConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{profile_id}/reset", response_model=InfrastructureProfileRead)
async def reset_profile(
    profile_id: str,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> InfrastructureProfileRead:
    try:
        return await service.reset_profile(profile_id)
    except (ProfileNotFoundError, BuiltinProfileError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    profile_id: str,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> None:
    try:
        await service.delete_profile(profile_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except BuiltinProfileError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{profile_id}/apply", response_model=ProfileApplyRead, status_code=status.HTTP_201_CREATED)
async def apply_profile(
    profile_id: str,
    payload: ProfileApplyRequest,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileApplyRead:
    try:
        return await service.apply_profile(profile_id, payload)
    except (ProfileNotFoundError, JobTargetNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobTargetNotManagedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (ProfileStepResolutionError, DeploymentValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DeploymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except VariableResolutionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except CredentialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

````

## backend/app/modules/profiles/tasks.py

``python
"""Future background tasks for profile application workflows."""

````

## backend/app/modules/packages/models.py

``python
from enum import StrEnum
from uuid import UUID

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class PackageInstallStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PackageInstallation(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "package_installations"

    server_id: Mapped[UUID] = mapped_column(ForeignKey("servers.id"), index=True)
    package_name: Mapped[str] = mapped_column(String(255))
    package_manager: Mapped[str] = mapped_column(String(50))
    requested_version: Mapped[str | None] = mapped_column(String(100))
    output: Mapped[str | None] = mapped_column(Text)
    status: Mapped[PackageInstallStatus] = mapped_column(
        Enum(PackageInstallStatus),
        default=PackageInstallStatus.PENDING,
    )


class PackageDefinitionRecord(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "package_definitions"
    __table_args__ = (UniqueConstraint("slug", name="uq_package_definitions_slug"),)

    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    supported_os: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    install_command: Mapped[str] = mapped_column(Text, nullable=False)
    uninstall_command: Mapped[str] = mapped_column(Text, default="", nullable=False)
    validation_command: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_modified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    base_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_template_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

````

## backend/app/modules/packages/schemas.py

``python
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

````

## backend/app/modules/packages/repository.py

``python
from backend.app.common.repository import BaseRepository
from backend.app.modules.packages.models import PackageDefinitionRecord, PackageInstallation

from sqlalchemy import delete, select
from uuid import UUID


class PackageInstallationRepository(BaseRepository[PackageInstallation]):
    pass


class PackageDefinitionRepository(BaseRepository[PackageDefinitionRecord]):
    async def create(self, definition: PackageDefinitionRecord) -> PackageDefinitionRecord:
        self.session.add(definition)
        await self.session.flush()
        await self.session.refresh(definition)
        return definition

    async def list(self) -> list[PackageDefinitionRecord]:
        result = await self.session.execute(
            select(PackageDefinitionRecord).order_by(PackageDefinitionRecord.name.asc())
        )
        return list(result.scalars().all())

    async def get_by_slug(self, slug: str) -> PackageDefinitionRecord | None:
        result = await self.session.execute(
            select(PackageDefinitionRecord).where(PackageDefinitionRecord.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, definition_id: UUID) -> PackageDefinitionRecord | None:
        result = await self.session.execute(
            select(PackageDefinitionRecord).where(PackageDefinitionRecord.id == definition_id)
        )
        return result.scalar_one_or_none()

    async def delete(self, definition: PackageDefinitionRecord) -> None:
        await self.session.execute(
            delete(PackageDefinitionRecord).where(PackageDefinitionRecord.id == definition.id)
        )

````

## backend/app/modules/packages/service.py

``python
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from backend.app.common.variables import VariableResolutionError, VariableResolutionService
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.jobs.schemas import BulkExecutionRead, JobBulkExecuteRequest, JobExecuteRequest, JobRead
from backend.app.modules.jobs.service import JobService
from backend.app.modules.packages.definitions import (
    PackageDefinition,
    get_package_definition,
    list_package_definitions,
)
from backend.app.modules.packages.models import PackageDefinitionRecord
from backend.app.modules.packages.repository import PackageDefinitionRepository
from backend.app.modules.packages.schemas import (
    PackageDefinitionCreate,
    PackageDefinitionRead,
    PackageDefinitionUpdate,
    PackageBulkApplyRequest,
    PackageCloneRequest,
    PackageExecuteRequest,
)


class PackageDefinitionNotFoundError(Exception):
    """Raised when a package definition cannot be found."""


class PackageDefinitionConflictError(Exception):
    """Raised when a package definition slug already exists."""


class BuiltinPackageDefinitionError(Exception):
    """Raised when trying to mutate a built-in package definition."""


SYSTEM_TEMPLATE_VERSION = "2026.05.16"


class PackageAutomationService:
    """Application service for reusable package definitions."""

    def __init__(
        self,
        *,
        repository: PackageDefinitionRepository | None = None,
        job_service: JobService | None = None,
        credential_service: CredentialService | None = None,
    ) -> None:
        self.repository = repository
        self.job_service = job_service
        self.credential_service = credential_service
        self.variable_service = VariableResolutionService()

    async def list_definitions(self) -> list[PackageDefinitionRead]:
        definitions = [self._builtin_to_read(definition) for definition in list_package_definitions()]
        if self.repository is None:
            return definitions

        custom_definitions = [self._record_to_read(record) for record in await self.repository.list()]
        custom_ids = {definition.id for definition in custom_definitions}
        return [definition for definition in definitions if definition.id not in custom_ids] + custom_definitions

    async def get_definition(self, package_id: str) -> PackageDefinitionRead:
        if self.repository is not None:
            record = await self.repository.get_by_slug(package_id)
            if record is not None:
                return self._record_to_read(record)

        definition = get_package_definition(package_id)
        if definition is None:
            raise PackageDefinitionNotFoundError("Package definition not found")
        return self._builtin_to_read(definition)

    async def create_definition(self, payload: PackageDefinitionCreate) -> PackageDefinitionRead:
        if self.repository is None:
            raise RuntimeError("Package definition repository is required")

        if get_package_definition(payload.id) or await self.repository.get_by_slug(payload.id):
            raise PackageDefinitionConflictError("Package definition already exists")

        record = PackageDefinitionRecord(
            slug=payload.id,
            name=payload.name,
            category=payload.category,
            supported_os=payload.supported_os,
            install_command=payload.install_command,
            uninstall_command=payload.uninstall_command,
            validation_command=payload.validation_command,
            variables=[variable.model_dump() for variable in payload.variables],
            tags=payload.tags,
            description=payload.description,
            is_builtin=False,
        )
        try:
            record = await self.repository.create(record)
            await self.repository.session.commit()
        except IntegrityError as exc:
            await self.repository.session.rollback()
            raise PackageDefinitionConflictError("Package definition already exists") from exc
        return self._record_to_read(record)

    async def update_definition(
        self,
        package_id: str,
        payload: PackageDefinitionUpdate,
    ) -> PackageDefinitionRead:
        if self.repository is None:
            raise RuntimeError("Package definition repository is required")

        record = await self.repository.get_by_slug(package_id)
        builtin = get_package_definition(package_id)
        if record is None and builtin is not None:
            record = await self._create_builtin_override(builtin)
        if record is None:
            raise PackageDefinitionNotFoundError("Package definition not found")

        for key, value in payload.model_dump(exclude_unset=True).items():
            if key == "variables" and value is not None:
                value = [item.model_dump() if hasattr(item, "model_dump") else item for item in value]
            setattr(record, key, value)
        record.is_modified = True
        record.modified_at = datetime.now(UTC)

        await self.repository.session.commit()
        await self.repository.session.refresh(record)
        return self._record_to_read(record)

    async def delete_definition(self, package_id: str) -> None:
        if self.repository is None:
            raise RuntimeError("Package definition repository is required")

        if get_package_definition(package_id):
            raise BuiltinPackageDefinitionError("Built-in package definitions cannot be deleted")

        record = await self.repository.get_by_slug(package_id)
        if record is None:
            raise PackageDefinitionNotFoundError("Package definition not found")

        await self.repository.delete(record)
        await self.repository.session.commit()

    async def clone_definition(self, package_id: str, payload: PackageCloneRequest) -> PackageDefinitionRead:
        if self.repository is None:
            raise RuntimeError("Package definition repository is required")
        if get_package_definition(payload.id) or await self.repository.get_by_slug(payload.id):
            raise PackageDefinitionConflictError("Package definition already exists")

        source = await self.get_definition(package_id)
        record = PackageDefinitionRecord(
            slug=payload.id,
            name=payload.name or f"{source.name} Copy",
            category=source.category,
            supported_os=source.supported_os,
            install_command=source.install_command,
            uninstall_command=source.uninstall_command,
            validation_command=source.validation_command,
            variables=[variable.model_dump() for variable in source.variables],
            tags=[*source.tags, "cloned"],
            description=source.description,
            is_builtin=False,
            is_modified=False,
            base_version=source.base_version,
            source_template_id=source.id,
        )
        try:
            record = await self.repository.create(record)
            await self.repository.session.commit()
        except IntegrityError as exc:
            await self.repository.session.rollback()
            raise PackageDefinitionConflictError("Package definition already exists") from exc
        return self._record_to_read(record)

    async def reset_definition(self, package_id: str) -> PackageDefinitionRead:
        if self.repository is None:
            raise RuntimeError("Package definition repository is required")
        if get_package_definition(package_id) is None:
            raise BuiltinPackageDefinitionError("Only built-in package definitions can be reset")
        record = await self.repository.get_by_slug(package_id)
        if record is not None:
            await self.repository.delete(record)
            await self.repository.session.commit()
        return await self.get_definition(package_id)

    async def execute_definition(self, package_id: str, payload: PackageExecuteRequest) -> JobRead:
        if self.job_service is None:
            raise RuntimeError("Job service is required")

        definition = await self.get_definition(package_id)
        command, redacted_command = await self._resolve_definition_commands(
            definition,
            payload.variables,
            payload.credential_refs,
        )
        return await self.job_service.execute(
            JobExecuteRequest(
                target_server_id=payload.target_server_id,
                operation_type=f"package:{definition.id}",
                command=command,
                redacted_command=redacted_command,
            )
        )

    async def execute_definition_bulk(self, payload: PackageBulkApplyRequest) -> BulkExecutionRead:
        if self.job_service is None:
            raise RuntimeError("Job service is required")

        definition = await self.get_definition(payload.package_id)
        command, redacted_command = await self._resolve_definition_commands(
            definition,
            payload.variables,
            payload.credential_refs,
        )
        return await self.job_service.execute_bulk(
            JobBulkExecuteRequest(
                target_server_ids=payload.target_server_ids,
                operation_type=f"package:{definition.id}",
                command=command,
                redacted_command=redacted_command,
            )
        )

    @staticmethod
    def _builtin_to_read(definition: PackageDefinition) -> PackageDefinitionRead:
        return PackageDefinitionRead(
            **definition.__dict__,
            is_builtin=True,
            is_modified=False,
            base_version=SYSTEM_TEMPLATE_VERSION,
        )

    @staticmethod
    def _record_to_read(record: PackageDefinitionRecord) -> PackageDefinitionRead:
        return PackageDefinitionRead(
            id=record.slug,
            name=record.name,
            category=record.category,
            supported_os=record.supported_os,
            install_command=record.install_command,
            uninstall_command=record.uninstall_command,
            validation_command=record.validation_command,
            variables=record.variables,
            tags=record.tags,
            description=record.description,
            is_builtin=record.is_builtin,
            is_modified=record.is_modified,
            base_version=record.base_version,
            source_template_id=record.source_template_id,
            modified_at=record.modified_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    async def _create_builtin_override(self, definition: PackageDefinition) -> PackageDefinitionRecord:
        assert self.repository is not None
        record = PackageDefinitionRecord(
            slug=definition.id,
            name=definition.name,
            category=definition.category,
            supported_os=definition.supported_os,
            install_command=definition.install_command,
            uninstall_command=definition.uninstall_command,
            validation_command=definition.validation_command,
            variables=definition.variables,
            tags=definition.tags,
            description=definition.description,
            is_builtin=True,
            is_modified=False,
            base_version=SYSTEM_TEMPLATE_VERSION,
            source_template_id=definition.id,
        )
        record = await self.repository.create(record)
        await self.repository.session.flush()
        return record

    def _resolve_definition_command(
        self,
        definition: PackageDefinitionRead,
        variables: dict[str, str],
    ) -> str:
        try:
            install = self.variable_service.resolve_text(
                definition.install_command,
                definitions=[variable.model_dump() for variable in definition.variables],
                variables=variables,
            )
            validation = self.variable_service.resolve_text(
                definition.validation_command,
                definitions=[variable.model_dump() for variable in definition.variables],
                variables=variables,
            )
        except VariableResolutionError:
            raise
        return f"{install} && {validation}"

    async def _resolve_definition_commands(
        self,
        definition: PackageDefinitionRead,
        variables: dict[str, str],
        credential_refs: dict[str, str],
    ) -> tuple[str, str]:
        definitions = [variable.model_dump() for variable in definition.variables]
        secret_values = await self._resolve_secret_variables(definitions, credential_refs)
        safe_variables = self._without_sensitive_plaintext(definitions, variables, credential_refs)
        runtime_variables = {**safe_variables, **secret_values}
        redacted_variables = {**safe_variables, **{name: "********" for name in secret_values}}

        install = self.variable_service.resolve_text(
            definition.install_command,
            definitions=definitions,
            variables=runtime_variables,
        )
        validation = self.variable_service.resolve_text(
            definition.validation_command,
            definitions=definitions,
            variables=runtime_variables,
        )
        redacted_install = self.variable_service.resolve_text(
            definition.install_command,
            definitions=definitions,
            variables=redacted_variables,
        )
        redacted_validation = self.variable_service.resolve_text(
            definition.validation_command,
            definitions=definitions,
            variables=redacted_variables,
        )
        return f"{install} && {validation}", f"{redacted_install} && {redacted_validation}"

    async def _resolve_secret_variables(
        self,
        definitions: list[dict],
        credential_refs: dict[str, str],
    ) -> dict[str, str]:
        secret_values: dict[str, str] = {}
        sensitive_names = [str(item["name"]) for item in definitions if item.get("name") and item.get("sensitive")]
        for name in sensitive_names:
            credential_ref = credential_refs.get(name)
            if not credential_ref:
                definition = next(item for item in definitions if item.get("name") == name)
                if definition.get("required"):
                    raise VariableResolutionError(f"Sensitive variable {name} requires a credential reference")
                continue
            if self.credential_service is None:
                raise VariableResolutionError("Credential service is required for sensitive package variables")
            credential = await self.credential_service.resolve_credential(credential_ref)
            secret = credential.secret or credential.private_key
            if not secret:
                raise VariableResolutionError(f"Credential reference for {name} has no usable secret value")
            secret_values[name] = secret
        return secret_values

    @staticmethod
    def _without_sensitive_plaintext(
        definitions: list[dict],
        variables: dict[str, str],
        credential_refs: dict[str, str],
    ) -> dict[str, str]:
        sensitive_names = {str(item["name"]) for item in definitions if item.get("name") and item.get("sensitive")}
        unsafe = sorted(name for name in sensitive_names if variables.get(name) and not credential_refs.get(name))
        if unsafe:
            raise VariableResolutionError(
                "Sensitive variable(s) must use credential references: " + ", ".join(unsafe)
            )
        return {name: value for name, value in variables.items() if name not in sensitive_names}

````

## backend/app/modules/packages/router.py

``python
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.ssh import ParamikoSshAdapter
from backend.app.db.session import AsyncSessionLocal, get_db_session
from backend.app.modules.audit.repository import AuditEventRepository
from backend.app.modules.audit.service import AuditService
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.service import CredentialNotFoundError, CredentialService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.jobs.repository import JobRepository
from backend.app.modules.jobs.schemas import BulkExecutionRead, JobRead
from backend.app.modules.jobs.service import JobService, JobTargetNotFoundError, JobTargetNotManagedError
from backend.app.modules.packages.repository import PackageDefinitionRepository
from backend.app.modules.packages.schemas import PackageDefinitionRead
from backend.app.modules.packages.schemas import (
    PackageCloneRequest,
    PackageDefinitionCreate,
    PackageDefinitionUpdate,
    PackageBulkApplyRequest,
    PackageExecuteRequest,
)
from backend.app.common.variables import VariableResolutionError
from backend.app.modules.packages.service import (
    BuiltinPackageDefinitionError,
    PackageAutomationService,
    PackageDefinitionConflictError,
    PackageDefinitionNotFoundError,
)

router = APIRouter()


async def get_package_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PackageAutomationService:
    return PackageAutomationService(
        repository=PackageDefinitionRepository(session),
        job_service=JobService(
            job_repository=JobRepository(session),
            server_repository=ServerRepository(session),
            ssh_adapter=ParamikoSshAdapter(),
            credential_service=CredentialService(repository=CredentialRepository(session)),
            audit_service=AuditService(AuditEventRepository(session)),
            session_factory=AsyncSessionLocal,
        ),
        credential_service=CredentialService(repository=CredentialRepository(session)),
    )


@router.get("", response_model=list[PackageDefinitionRead])
async def list_package_definitions(
    service: Annotated[PackageAutomationService, Depends(get_package_service)],
) -> list[PackageDefinitionRead]:
    return await service.list_definitions()


@router.post("/apply/bulk", response_model=BulkExecutionRead, status_code=status.HTTP_201_CREATED)
async def execute_package_bulk(
    payload: PackageBulkApplyRequest,
    service: Annotated[PackageAutomationService, Depends(get_package_service)],
) -> BulkExecutionRead:
    try:
        return await service.execute_definition_bulk(payload)
    except PackageDefinitionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except VariableResolutionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except CredentialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("", response_model=PackageDefinitionRead, status_code=status.HTTP_201_CREATED)
async def create_package_definition(
    payload: PackageDefinitionCreate,
    service: Annotated[PackageAutomationService, Depends(get_package_service)],
) -> PackageDefinitionRead:
    try:
        return await service.create_definition(payload)
    except PackageDefinitionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/{package_id}", response_model=PackageDefinitionRead)
async def get_package_definition(
    package_id: str,
    service: Annotated[PackageAutomationService, Depends(get_package_service)],
) -> PackageDefinitionRead:
    try:
        return await service.get_definition(package_id)
    except PackageDefinitionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/{package_id}", response_model=PackageDefinitionRead)
async def update_package_definition(
    package_id: str,
    payload: PackageDefinitionUpdate,
    service: Annotated[PackageAutomationService, Depends(get_package_service)],
) -> PackageDefinitionRead:
    try:
        return await service.update_definition(package_id, payload)
    except PackageDefinitionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except BuiltinPackageDefinitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{package_id}/clone", response_model=PackageDefinitionRead, status_code=status.HTTP_201_CREATED)
async def clone_package_definition(
    package_id: str,
    payload: PackageCloneRequest,
    service: Annotated[PackageAutomationService, Depends(get_package_service)],
) -> PackageDefinitionRead:
    try:
        return await service.clone_definition(package_id, payload)
    except PackageDefinitionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PackageDefinitionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{package_id}/reset", response_model=PackageDefinitionRead)
async def reset_package_definition(
    package_id: str,
    service: Annotated[PackageAutomationService, Depends(get_package_service)],
) -> PackageDefinitionRead:
    try:
        return await service.reset_definition(package_id)
    except (PackageDefinitionNotFoundError, BuiltinPackageDefinitionError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_package_definition(
    package_id: str,
    service: Annotated[PackageAutomationService, Depends(get_package_service)],
) -> None:
    try:
        await service.delete_definition(package_id)
    except PackageDefinitionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except BuiltinPackageDefinitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{package_id}/execute", response_model=JobRead, status_code=status.HTTP_201_CREATED)
async def execute_package_definition(
    package_id: str,
    payload: PackageExecuteRequest,
    service: Annotated[PackageAutomationService, Depends(get_package_service)],
) -> JobRead:
    try:
        return await service.execute_definition(package_id, payload)
    except PackageDefinitionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except VariableResolutionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except CredentialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobTargetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobTargetNotManagedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except JobTargetNotManagedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

````

## backend/app/modules/packages/tasks.py

``python
"""Future background tasks for package automation."""

````

## frontend/src/features/profiles/api/profilesApi.ts

``typescript
import { apiClient } from '../../../lib/api/client';
import type {
  ApplyProfilePayload,
  ApplyProfileBulkPayload,
  ApplyProfileBulkResult,
  ApplyProfileResult,
  CreateInfrastructureProfilePayload,
  InfrastructureProfile,
} from '../types/profile';

export async function listProfiles(): Promise<InfrastructureProfile[]> {
  const response = await apiClient.get<InfrastructureProfile[]>('/profiles');
  return response.data;
}

export async function applyProfile(
  profileId: string,
  payload: ApplyProfilePayload,
): Promise<ApplyProfileResult> {
  const response = await apiClient.post<ApplyProfileResult>(`/profiles/${profileId}/apply`, payload);
  return response.data;
}

export async function applyProfileBulk(payload: ApplyProfileBulkPayload): Promise<ApplyProfileBulkResult> {
  const response = await apiClient.post<ApplyProfileBulkResult>('/profiles/apply/bulk', payload);
  return response.data;
}

export async function createProfile(
  payload: CreateInfrastructureProfilePayload,
): Promise<InfrastructureProfile> {
  const response = await apiClient.post<InfrastructureProfile>('/profiles', payload);
  return response.data;
}

export async function updateProfile(
  profileId: string,
  payload: Partial<Omit<CreateInfrastructureProfilePayload, 'id'>>,
): Promise<InfrastructureProfile> {
  const response = await apiClient.put<InfrastructureProfile>(`/profiles/${profileId}`, payload);
  return response.data;
}

export async function cloneProfile(
  profileId: string,
  payload: { id: string; name?: string },
): Promise<InfrastructureProfile> {
  const response = await apiClient.post<InfrastructureProfile>(`/profiles/${profileId}/clone`, payload);
  return response.data;
}

export async function resetProfile(profileId: string): Promise<InfrastructureProfile> {
  const response = await apiClient.post<InfrastructureProfile>(`/profiles/${profileId}/reset`);
  return response.data;
}

export async function deleteProfile(profileId: string): Promise<void> {
  await apiClient.delete(`/profiles/${profileId}`);
}

````

## frontend/src/features/profiles/types/profile.ts

``typescript
import type { Job } from '../../jobs/types/job';

export type ProfileStep = {
  id: string;
  name: string;
  kind: 'action' | 'package' | 'command' | 'deployment' | 'script';
  reference_id: string;
  type?: 'action' | 'package' | 'deployment' | 'script' | null;
  target?: string | null;
  enabled?: boolean;
  credential_ref?: string | null;
  command?: string | null;
};

export type TemplateVariable = {
  name: string;
  description: string;
  default_value: string | null;
  required: boolean;
  sensitive: boolean;
  credential_type?: string | null;
};

export type InfrastructureProfile = {
  id: string;
  name: string;
  category: string;
  description: string;
  tags: string[];
  steps: ProfileStep[];
  variables: TemplateVariable[];
  is_builtin: boolean;
  is_modified: boolean;
  base_version: string | null;
  source_template_id: string | null;
  modified_at: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type CreateInfrastructureProfilePayload = {
  id: string;
  name: string;
  category: string;
  description: string;
  tags: string[];
  steps: ProfileStep[];
  variables: TemplateVariable[];
};

export type ApplyProfilePayload = {
  target_server_id: string;
  stop_on_failure: boolean;
  variables?: Record<string, string>;
  credential_refs?: Record<string, string>;
};

export type ApplyProfileResult = {
  profile_id: string;
  target_server_id: string;
  status: string;
  jobs: Job[];
  message: string;
};

export type ApplyProfileBulkPayload = {
  profile_id: string;
  target_server_ids: string[];
  stop_on_failure: boolean;
  variables?: Record<string, string>;
  credential_refs?: Record<string, string>;
};

export type ApplyProfileBulkResult = {
  profile_id: string;
  success_count: number;
  failure_count: number;
  results: Array<{
    target_server_id: string;
    target_hostname: string | null;
    success: boolean;
    result: ApplyProfileResult | null;
    error: string | null;
  }>;
};

````

## frontend/src/features/profiles/ProfilesPage.tsx

``tsx
import { useCallback, useEffect, useMemo, useState } from 'react';
import type { DragEvent } from 'react';
import { ArrowDown, ArrowUp, Package, Play, Plus, Trash2, Terminal } from 'lucide-react';

import { ContextDrawer } from '../../components/ContextDrawer';
import { PageHeader } from '../../components/layout/PageHeader';
import { PageActionButton } from '../../components/operations/OperationalComponents';
import {
  ExecutionVariablesModal,
  type ExecutionVariableValues,
} from '../../components/ExecutionVariablesModal';
import { VariableDefinitionEditor } from '../../components/VariableDefinitionEditor';
import { getApiErrorMessage } from '../../lib/api/client';
import { listCredentials } from '../credentials/api/credentialsApi';
import type { Credential } from '../credentials/types/credential';
import { listDeployments } from '../deployments/api/deploymentsApi';
import type { Deployment } from '../deployments/types/deployment';
import { listServers } from '../inventory/api/serversApi';
import { TargetSelector } from '../inventory/components/TargetSelector';
import { useTargetSelection } from '../inventory/hooks/useTargetSelection';
import type { Server } from '../inventory/types/server';
import { listOperationalActions } from '../jobs/api/jobsApi';
import { JobStatusBadge } from '../jobs/components/JobStatusBadge';
import type { OperationalAction } from '../jobs/types/job';
import { listPackageDefinitions } from '../packages/api/packagesApi';
import type { PackageDefinition } from '../packages/types/package';
import {
  applyProfile,
  applyProfileBulk,
  cloneProfile,
  createProfile,
  deleteProfile,
  listProfiles,
  resetProfile,
  updateProfile,
} from './api/profilesApi';
import type {
  ApplyProfileBulkResult,
  ApplyProfileResult,
  CreateInfrastructureProfilePayload,
  InfrastructureProfile,
  ProfileStep,
} from './types/profile';

type ProfileFormState = Omit<CreateInfrastructureProfilePayload, 'tags' | 'steps' | 'variables'> & {
  tags_text: string;
  steps: ProfileStep[];
  variables: CreateInfrastructureProfilePayload['variables'];
};

const initialProfileFormState: ProfileFormState = {
  id: '',
  name: '',
  category: '',
  description: '',
  tags_text: '',
  steps: [
    {
      id: 'package-docker-engine-1',
      kind: 'package',
      type: 'package',
      reference_id: 'docker-engine',
      target: 'docker-engine',
      name: 'Install Docker Engine',
      enabled: true,
    },
    {
      id: 'action-docker-status-2',
      kind: 'action',
      type: 'action',
      reference_id: 'docker-status',
      target: 'docker-status',
      name: 'Check Docker Service',
      enabled: true,
    },
  ],
  variables: [],
};

export function ProfilesPage() {
  const [profiles, setProfiles] = useState<InfrastructureProfile[]>([]);
  const [servers, setServers] = useState<Server[]>([]);
  const [packages, setPackages] = useState<PackageDefinition[]>([]);
  const [actions, setActions] = useState<OperationalAction[]>([]);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState('');
  const [selectedServerId, setSelectedServerId] = useState('');
  const [selectedServerIds, setSelectedServerIds] = useState<string[]>([]);
  const [formState, setFormState] = useState<ProfileFormState>(initialProfileFormState);
  const [result, setResult] = useState<ApplyProfileResult | null>(null);
  const [bulkResult, setBulkResult] = useState<ApplyProfileBulkResult | null>(null);
  const [isExecutionModalOpen, setIsExecutionModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isApplying, setIsApplying] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [editingProfileId, setEditingProfileId] = useState<string | null>(null);
  const [isBuilderOpen, setIsBuilderOpen] = useState(false);
  const targetSelector = useTargetSelection('single');

  const selectedProfile = useMemo(
    () => profiles.find((profile) => profile.id === selectedProfileId) ?? profiles[0] ?? null,
    [profiles, selectedProfileId],
  );

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const [
        nextProfiles,
        nextServers,
        nextPackages,
        nextActions,
        nextCredentials,
        nextDeployments,
      ] = await Promise.all([
        listProfiles(),
        listServers(),
        listPackageDefinitions(),
        listOperationalActions(),
        listCredentials(),
        listDeployments(),
      ]);
      setProfiles(nextProfiles);
      setServers(nextServers);
      setPackages(nextPackages);
      setActions(nextActions);
      setCredentials(nextCredentials);
      setDeployments(nextDeployments);
      setSelectedProfileId((current) => current || nextProfiles[0]?.id || '');
      setSelectedServerId((current) => current || nextServers[0]?.id || '');
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsLoading(false);
    }
  }, []);

  function updateField(name: keyof ProfileFormState, value: string) {
    setFormState((current) => ({ ...current, [name]: value }));
    setError(null);
    setSuccess(null);
  }

  function startEdit(profile: InfrastructureProfile) {
    setIsBuilderOpen(true);
    setEditingProfileId(profile.id);
    setFormState({
      id: profile.id,
      name: profile.name,
      category: profile.category,
      description: profile.description,
      tags_text: profile.tags.join(','),
      steps: normalizeProfileSteps(profile.steps),
      variables: profile.variables,
    });
    setError(null);
    setSuccess(null);
  }

  function resetEditor() {
    setEditingProfileId(null);
    setFormState(initialProfileFormState);
    setIsBuilderOpen(false);
  }

  async function handleCreateProfile() {
    if (!formState.id.trim() || !formState.name.trim()) {
      setError('Profile id and name are required.');
      return;
    }

    const steps = normalizeProfileSteps(formState.steps);
    if (steps.length === 0) {
      setError('Add at least one profile step.');
      return;
    }

    setIsCreating(true);
    setError(null);
    setSuccess(null);

    try {
      const payload = {
        name: formState.name.trim(),
        category: formState.category.trim() || 'Custom',
        description: formState.description.trim() || 'Custom infrastructure profile.',
        tags: splitCsv(formState.tags_text),
        steps,
        variables: formState.variables
          .filter((variable) => variable.name.trim())
          .map((variable) => ({
            ...variable,
            name: variable.name.trim(),
            description: variable.description.trim(),
          })),
      };
      if (editingProfileId) {
        const updated = await updateProfile(editingProfileId, payload);
        setProfiles((current) =>
          current.map((profile) => (profile.id === updated.id ? updated : profile)),
        );
        setSelectedProfileId(updated.id);
        setSuccess(`Updated profile ${updated.name}.`);
      } else {
        const created = await createProfile({ id: formState.id.trim(), ...payload });
        setProfiles((current) => [...current, created]);
        setSelectedProfileId(created.id);
        setSuccess(`Created profile ${created.name}.`);
      }
      resetEditor();
    } catch (caughtError) {
      setError(
        caughtError instanceof SyntaxError
          ? 'Variables must be valid JSON.'
          : getApiErrorMessage(caughtError),
      );
    } finally {
      setIsCreating(false);
    }
  }

  async function handleCloneProfile(profile: InfrastructureProfile) {
    const id = window.prompt('Clone profile as ID', `${profile.id}-copy`);
    if (!id) {
      return;
    }
    try {
      const cloned = await cloneProfile(profile.id, {
        id: id.trim(),
        name: `${profile.name} Copy`,
      });
      setProfiles((current) => [...current, cloned]);
      setSelectedProfileId(cloned.id);
      setSuccess(`Cloned profile ${cloned.name}.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    }
  }

  async function handleResetProfile(profile: InfrastructureProfile) {
    const confirmed = window.confirm(
      `Restore ${profile.name} to the built-in default? Current edits will be discarded.`,
    );
    if (!confirmed) {
      return;
    }
    try {
      const restored = await resetProfile(profile.id);
      setProfiles((current) => current.map((item) => (item.id === restored.id ? restored : item)));
      setSelectedProfileId(restored.id);
      setSuccess(`Restored profile ${restored.name} to default.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    }
  }

  async function handleDeleteProfile(profileId: string) {
    const confirmed = window.confirm(`Delete profile ${profileId}?`);
    if (!confirmed) {
      return;
    }

    try {
      await deleteProfile(profileId);
      setProfiles((current) => current.filter((profile) => profile.id !== profileId));
      setSelectedProfileId((current) => (current === profileId ? '' : current));
      setSuccess(`Deleted profile ${profileId}.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    }
  }

  function handleApplyProfile() {
    const profileId = selectedProfile?.id;
    if (!profileId || (!selectedServerId && selectedServerIds.length === 0)) {
      return;
    }
    setIsExecutionModalOpen(true);
  }

  async function runProfile(executionVariables: ExecutionVariableValues) {
    const profileId = selectedProfile?.id;
    if (!profileId) {
      return;
    }
    setIsApplying(true);
    setError(null);
    setResult(null);
    setBulkResult(null);

    try {
      if (selectedServerIds.length > 0) {
        setBulkResult(
          await applyProfileBulk({
            profile_id: profileId,
            target_server_ids: selectedServerIds,
            stop_on_failure: true,
            variables: executionVariables.variables,
            credential_refs: executionVariables.credential_refs,
          }),
        );
      } else {
        setResult(
          await applyProfile(profileId, {
            target_server_id: selectedServerId,
            stop_on_failure: true,
            variables: executionVariables.variables,
            credential_refs: executionVariables.credential_refs,
          }),
        );
      }
      setIsExecutionModalOpen(false);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsApplying(false);
    }
  }

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Infrastructure Profiles"
        description="Reusable infrastructure standards that apply ordered package and action workflows."
        actions={
          <PageActionButton icon={Plus} tone="secondary" onClick={() => setIsBuilderOpen(true)}>
            Create profile
          </PageActionButton>
        }
      />

      {error ? (
        <p className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          {error}
        </p>
      ) : null}
      {success ? (
        <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
          {success}
        </p>
      ) : null}
      {isLoading ? <LoadingGrid /> : null}

      {!isLoading && !error ? (
        <>
          <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
            <div className="grid gap-4 lg:grid-cols-[minmax(220px,0.8fr)_minmax(260px,1fr)_auto] lg:items-end">
              <label className="block">
                <span className="text-sm font-medium text-zinc-950">Profile</span>
                <select
                  className="mt-2 h-10 w-full rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-950 focus:ring-2 focus:ring-zinc-950/10"
                  value={selectedProfile?.id ?? ''}
                  onChange={(event) => setSelectedProfileId(event.target.value)}
                >
                  {profiles.map((profile) => (
                    <option key={profile.id} value={profile.id}>
                      {profile.name}
                    </option>
                  ))}
                </select>
              </label>

              <button
                className="inline-flex h-10 items-center justify-center rounded-md bg-zinc-950 px-4 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
                disabled={
                  !selectedProfile ||
                  (!selectedServerId && selectedServerIds.length === 0) ||
                  isApplying
                }
                type="button"
                onClick={handleApplyProfile}
              >
                {isApplying
                  ? 'Applying'
                  : selectedServerIds.length > 0
                    ? `Apply to ${selectedServerIds.length}`
                    : 'Apply profile'}
              </button>
            </div>

            <div className="mt-4">
              <TargetSelector
                servers={servers}
                eligibility="profiles"
                selection={{
                  mode: targetSelector.selection.mode,
                  selectedId: selectedServerId,
                  selectedIds: selectedServerIds,
                }}
                filters={targetSelector.filters}
                title="Profile targets"
                description="Apply this profile to one host or a filtered group of inventory hosts."
                onFiltersChange={targetSelector.setFilters}
                onSelectionChange={(selection) => {
                  targetSelector.setMode(selection.mode);
                  setSelectedServerId(selection.selectedId);
                  setSelectedServerIds(selection.selectedIds);
                }}
              />
            </div>
          </section>

          <ContextDrawer
            description="Profiles are orchestration blueprints: ordered package, deployment, action, and command standards."
            isOpen={isBuilderOpen}
            title={editingProfileId ? 'Edit Profile' : 'Create Profile'}
            width="xl"
            onClose={resetEditor}
          >
            <ProfileBuilder
              actions={actions}
              formState={formState}
              credentials={credentials}
              deployments={deployments}
              editingProfileId={editingProfileId}
              isCreating={isCreating}
              packages={packages}
              onCreate={handleCreateProfile}
              onCancel={resetEditor}
              onFieldChange={updateField}
              onStepsChange={(steps) => setFormState((current) => ({ ...current, steps }))}
              onVariablesChange={(variables) =>
                setFormState((current) => ({ ...current, variables }))
              }
            />
          </ContextDrawer>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.8fr)]">
            <div className="grid gap-4">
              {profiles.map((profile) => (
                <ProfileCard
                  key={profile.id}
                  isSelected={selectedProfile?.id === profile.id}
                  profile={profile}
                  onDelete={handleDeleteProfile}
                  onClone={handleCloneProfile}
                  onEdit={startEdit}
                  onReset={handleResetProfile}
                  onSelect={() => setSelectedProfileId(profile.id)}
                />
              ))}
            </div>
            <div className="space-y-4">
              <ProfileResult result={result} />
              <BulkProfileResult result={bulkResult} />
            </div>
          </div>
        </>
      ) : null}
      <ExecutionVariablesModal
        credentials={credentials}
        isLoading={isApplying}
        isOpen={isExecutionModalOpen && selectedProfile !== null}
        previewItems={
          selectedProfile?.steps
            .filter((step) => step.enabled !== false)
            .map((step) => step.name) ?? []
        }
        targetLabel={`${selectedServerIds.length || 1} host(s) selected`}
        title={selectedProfile ? `Apply ${selectedProfile.name}` : 'Apply profile'}
        variables={selectedProfile?.variables ?? []}
        onCancel={() => setIsExecutionModalOpen(false)}
        onConfirm={runProfile}
      />
    </div>
  );
}

function BulkProfileResult({ result }: { result: ApplyProfileBulkResult | null }) {
  if (!result) {
    return null;
  }

  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-zinc-950">Bulk profile result</h3>
      <p className="mt-1 text-sm text-zinc-500">
        {result.success_count} succeeded, {result.failure_count} failed
      </p>
      <div className="mt-4 divide-y divide-zinc-100 rounded-md border border-zinc-200">
        {result.results.map((item) => (
          <div key={item.target_server_id} className="px-3 py-2 text-sm">
            <span
              className={
                item.success ? 'font-semibold text-emerald-700' : 'font-semibold text-rose-700'
              }
            >
              {item.success ? 'Success' : 'Failed'}
            </span>
            <span className="ml-2 text-zinc-700">
              {item.target_hostname ?? item.target_server_id}
            </span>
            {item.result ? (
              <p className="mt-1 text-xs text-zinc-500">
                {item.result.jobs.length} job(s), status {item.result.status}
              </p>
            ) : null}
            {item.error ? (
              <p className="mt-1 font-mono text-xs text-zinc-500">{item.error}</p>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}

function ProfileCard({
  profile,
  isSelected,
  onDelete,
  onClone,
  onEdit,
  onReset,
  onSelect,
}: {
  profile: InfrastructureProfile;
  isSelected: boolean;
  onDelete: (profileId: string) => void;
  onClone: (profile: InfrastructureProfile) => void;
  onEdit: (profile: InfrastructureProfile) => void;
  onReset: (profile: InfrastructureProfile) => void;
  onSelect: () => void;
}) {
  return (
    <article
      className={`rounded-lg border bg-white p-5 shadow-sm transition hover:border-zinc-300 hover:shadow-md ${isSelected ? 'border-zinc-950 ring-1 ring-zinc-950' : 'border-zinc-200'}`}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h3 className="text-lg font-semibold text-zinc-950">{profile.name}</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-600">{profile.description}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="inline-flex w-fit rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-700 ring-1 ring-inset ring-zinc-200">
            {profile.category}
          </span>
          <span className="inline-flex w-fit rounded-full bg-zinc-50 px-2.5 py-1 text-xs font-medium text-zinc-600 ring-1 ring-inset ring-zinc-200">
            {profile.is_builtin ? 'Built-in' : 'Custom'}
          </span>
          {profile.is_modified ? <Badge label="Modified" /> : null}
          {profile.source_template_id && !profile.is_builtin ? <Badge label="Cloned" /> : null}
        </div>
      </div>

      <ol className="mt-5 space-y-2 rounded-md border border-zinc-200 bg-zinc-50 p-3">
        {profile.steps.map((step, index) => (
          <li
            key={step.id}
            className="flex items-center gap-3 rounded-md bg-white px-2 py-2 text-sm text-zinc-700 ring-1 ring-zinc-100"
          >
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-zinc-950 text-xs font-semibold text-white">
              {index + 1}
            </span>
            <span>{step.name}</span>
            <span className="rounded-full bg-zinc-50 px-2 py-0.5 text-xs text-zinc-500 ring-1 ring-zinc-200">
              {step.kind}
            </span>
            {step.kind === 'command' ? (
              <span className="truncate font-mono text-xs text-zinc-500">{step.command}</span>
            ) : null}
          </li>
        ))}
      </ol>
      {profile.variables.length ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {profile.variables.map((variable) => (
            <span
              key={variable.name}
              className="rounded bg-zinc-100 px-2 py-1 font-mono text-xs text-zinc-700"
            >
              {variable.name}
              {variable.required ? ' *' : ''}
              {variable.sensitive ? ' sensitive' : ''}
            </span>
          ))}
        </div>
      ) : null}
      <div className="mt-5 flex flex-wrap justify-end gap-2">
        <button
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50"
          type="button"
          onClick={() => onClone(profile)}
        >
          Clone
        </button>
        <button
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50"
          type="button"
          onClick={() => onEdit(profile)}
        >
          Edit
        </button>
        {profile.is_builtin && profile.is_modified ? (
          <button
            className="rounded-md border border-amber-300 px-3 py-2 text-sm font-semibold text-amber-700 transition hover:bg-amber-50"
            type="button"
            onClick={() => onReset(profile)}
          >
            Restore default
          </button>
        ) : null}
        {!profile.is_builtin ? (
          <button
            className="rounded-md border border-rose-300 px-3 py-2 text-sm font-semibold text-rose-700 transition hover:bg-rose-50"
            type="button"
            onClick={() => onDelete(profile.id)}
          >
            Delete
          </button>
        ) : null}
        <button
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50"
          type="button"
          onClick={onSelect}
        >
          Select
        </button>
      </div>
    </article>
  );
}

function ProfileBuilder({
  actions,
  credentials,
  deployments,
  formState,
  editingProfileId,
  isCreating,
  packages,
  onCreate,
  onCancel,
  onFieldChange,
  onStepsChange,
  onVariablesChange,
}: {
  actions: OperationalAction[];
  credentials: Credential[];
  deployments: Deployment[];
  formState: ProfileFormState;
  editingProfileId: string | null;
  isCreating: boolean;
  packages: PackageDefinition[];
  onCreate: () => void;
  onCancel: () => void;
  onFieldChange: (name: keyof ProfileFormState, value: string) => void;
  onStepsChange: (steps: ProfileStep[]) => void;
  onVariablesChange: (variables: ProfileFormState['variables']) => void;
}) {
  const previewSteps = normalizeProfileSteps(formState.steps);

  function reorderSteps(from: number, to: number) {
    if (from === to) {
      return;
    }
    const next = [...previewSteps];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    onStepsChange(next);
  }

  function updateStep(index: number, patch: Partial<ProfileStep>) {
    const next = [...previewSteps];
    const current = next[index];
    const kind = (patch.kind ?? current.kind) as ProfileStep['kind'];
    const referenceId = patch.reference_id ?? patch.target ?? current.reference_id;
    next[index] = {
      ...current,
      ...patch,
      kind,
      type: kind === 'command' ? 'script' : kind === 'script' ? 'script' : kind,
      reference_id: referenceId,
      target: referenceId,
      id: patch.id ?? current.id,
    };
    onStepsChange(next);
  }

  function addStep() {
    const index = previewSteps.length + 1;
    onStepsChange([
      ...previewSteps,
      {
        id: `package-${index}`,
        kind: 'package',
        type: 'package',
        reference_id: packages[0]?.id ?? '',
        target: packages[0]?.id ?? '',
        name: packages[0]?.name ?? 'Package step',
        enabled: true,
      },
    ]);
  }

  function removeStep(index: number) {
    onStepsChange(previewSteps.filter((_, currentIndex) => currentIndex !== index));
  }

  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-zinc-950">
        {editingProfileId ? 'Edit profile' : 'Build profile'}
      </h3>
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <TextInput
          label="ID"
          name="id"
          placeholder="custom-profile"
          value={formState.id}
          onChange={onFieldChange}
        />
        <TextInput
          label="Name"
          name="name"
          placeholder="Custom Profile"
          value={formState.name}
          onChange={onFieldChange}
        />
        <TextInput
          label="Category"
          name="category"
          placeholder="Baseline"
          value={formState.category}
          onChange={onFieldChange}
        />
        <TextInput
          label="Tags"
          name="tags_text"
          placeholder="baseline,linux"
          value={formState.tags_text}
          onChange={onFieldChange}
        />
        <TextInput
          label="Description"
          name="description"
          placeholder="Reusable host standard"
          value={formState.description}
          onChange={onFieldChange}
        />
        <div className="xl:col-span-3">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-semibold uppercase text-zinc-500">Execution steps</p>
            <button
              className="inline-flex items-center gap-2 rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
              type="button"
              onClick={addStep}
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
              Add step
            </button>
          </div>
          <ol className="mt-3 space-y-3">
            {previewSteps.map((step, index) => (
              <ProfileStepCard
                key={`${step.id}-${index}`}
                actions={actions}
                credentials={credentials}
                deployments={deployments}
                index={index}
                packages={packages}
                step={step}
                total={previewSteps.length}
                onMove={reorderSteps}
                onRemove={() => removeStep(index)}
                onUpdate={(patch) => updateStep(index, patch)}
              />
            ))}
          </ol>
        </div>
        <VariableDefinitionEditor variables={formState.variables} onChange={onVariablesChange} />
      </div>
      <div className="mt-4 grid gap-4 text-xs text-zinc-500 lg:grid-cols-2">
        <ReferenceList
          label="Package refs"
          values={packages.map((packageDefinition) => packageDefinition.id)}
        />
        <ReferenceList label="Action refs" values={actions.map((action) => action.id)} />
        <ReferenceList
          label="Deployment refs"
          values={deployments.map((deployment) => deployment.id)}
        />
      </div>
      <div className="mt-4 flex justify-end gap-2">
        {editingProfileId ? (
          <button
            className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50"
            type="button"
            onClick={onCancel}
          >
            Cancel
          </button>
        ) : null}
        <button
          className="rounded-md bg-zinc-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:bg-zinc-300"
          disabled={isCreating}
          type="button"
          onClick={onCreate}
        >
          {isCreating ? 'Saving' : editingProfileId ? 'Save profile' : 'Create profile'}
        </button>
      </div>
    </section>
  );
}

function ReferenceList({ label, values }: { label: string; values: string[] }) {
  return (
    <div>
      <div className="font-semibold text-zinc-700">{label}</div>
      <div className="mt-1 flex flex-wrap gap-1">
        {values.map((value) => (
          <span key={value} className="rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-zinc-600">
            {value}
          </span>
        ))}
      </div>
    </div>
  );
}

function ProfileStepCard({
  actions,
  credentials,
  deployments,
  index,
  packages,
  step,
  total,
  onMove,
  onRemove,
  onUpdate,
}: {
  actions: OperationalAction[];
  credentials: Credential[];
  deployments: Deployment[];
  index: number;
  packages: PackageDefinition[];
  step: ProfileStep;
  total: number;
  onMove: (from: number, to: number) => void;
  onRemove: () => void;
  onUpdate: (patch: Partial<ProfileStep>) => void;
}) {
  const stepType = step.kind === 'command' ? 'script' : step.kind;
  const options =
    stepType === 'action' ? actions : stepType === 'deployment' ? deployments : packages;
  const Icon = stepType === 'package' ? Package : stepType === 'action' ? Play : Terminal;

  function handleTypeChange(value: string) {
    const nextKind = value === 'script' ? 'command' : (value as ProfileStep['kind']);
    const nextOptions =
      value === 'action' ? actions : value === 'deployment' ? deployments : packages;
    const first = nextOptions[0];
    onUpdate({
      kind: nextKind,
      type: value as ProfileStep['type'],
      reference_id: value === 'script' ? step.id : (first?.id ?? ''),
      target: value === 'script' ? step.id : (first?.id ?? ''),
      name: value === 'script' ? 'Script step' : (first?.name ?? ''),
      command: value === 'script' ? (step.command ?? '') : null,
    });
  }

  function handleTargetChange(value: string) {
    const selected = options.find((option) => option.id === value);
    onUpdate({ reference_id: value, target: value, name: selected?.name ?? value });
  }

  return (
    <li
      className={`rounded-md border bg-white p-4 ${step.enabled === false ? 'border-zinc-200 opacity-60' : 'border-zinc-300'}`}
      draggable
      onDragStart={(event: DragEvent<HTMLLIElement>) =>
        event.dataTransfer.setData('text/plain', String(index))
      }
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        onMove(Number(event.dataTransfer.getData('text/plain')), index);
      }}
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        <div className="flex items-center gap-3 lg:w-56">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-zinc-950 text-white">
            <Icon className="h-4 w-4" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-zinc-950">{step.name}</p>
            <p className="text-xs text-zinc-500">Step {index + 1}</p>
          </div>
        </div>

        <div className="grid flex-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          <label className="text-xs font-medium text-zinc-700">
            Type
            <select
              className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-2 py-2 text-sm"
              value={stepType}
              onChange={(event) => handleTypeChange(event.target.value)}
            >
              <option value="package">Package</option>
              <option value="action">Action</option>
              <option value="deployment">Deployment</option>
              <option value="script">Script</option>
            </select>
          </label>

          {stepType === 'script' ? (
            <label className="text-xs font-medium text-zinc-700 md:col-span-2">
              Command
              <input
                className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-2 py-2 font-mono text-sm"
                value={step.command ?? ''}
                onChange={(event) => onUpdate({ command: event.target.value, name: 'Script step' })}
              />
            </label>
          ) : (
            <label className="text-xs font-medium text-zinc-700 md:col-span-2">
              Target
              <select
                className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-2 py-2 text-sm"
                value={step.reference_id}
                onChange={(event) => handleTargetChange(event.target.value)}
              >
                {options.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.name}
                  </option>
                ))}
              </select>
            </label>
          )}

          <label className="text-xs font-medium text-zinc-700">
            Credential
            <select
              className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-2 py-2 text-sm"
              value={step.credential_ref ?? ''}
              onChange={(event) => onUpdate({ credential_ref: event.target.value || null })}
            >
              <option value="">None</option>
              {credentials.map((credential) => (
                <option key={credential.id} value={credential.id}>
                  {credential.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="flex flex-wrap justify-end gap-2">
          <label className="inline-flex h-9 items-center gap-2 rounded-md border border-zinc-300 px-3 text-sm font-medium text-zinc-700">
            <input
              checked={step.enabled !== false}
              type="checkbox"
              onChange={(event) => onUpdate({ enabled: event.target.checked })}
            />
            Enabled
          </label>
          <button
            className="rounded-md border border-zinc-300 p-2 text-zinc-700 disabled:opacity-40"
            disabled={index === 0}
            type="button"
            onClick={() => onMove(index, index - 1)}
            title="Move up"
          >
            <ArrowUp className="h-4 w-4" aria-hidden="true" />
          </button>
          <button
            className="rounded-md border border-zinc-300 p-2 text-zinc-700 disabled:opacity-40"
            disabled={index === total - 1}
            type="button"
            onClick={() => onMove(index, index + 1)}
            title="Move down"
          >
            <ArrowDown className="h-4 w-4" aria-hidden="true" />
          </button>
          <button
            className="rounded-md border border-rose-300 p-2 text-rose-700 hover:bg-rose-50"
            type="button"
            onClick={onRemove}
            title="Remove step"
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>
    </li>
  );
}

function Badge({ label }: { label: string }) {
  return (
    <span className="inline-flex w-fit rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700 ring-1 ring-inset ring-amber-200">
      {label}
    </span>
  );
}

function TextInput({
  label,
  name,
  value,
  placeholder,
  onChange,
}: {
  label: string;
  name: keyof ProfileFormState;
  value: string;
  placeholder: string;
  onChange: (name: keyof ProfileFormState, value: string) => void;
}) {
  return (
    <label className="text-sm font-medium text-zinc-700">
      {label}
      <input
        className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10"
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(name, event.target.value)}
      />
    </label>
  );
}

function ProfileResult({ result }: { result: ApplyProfileResult | null }) {
  if (!result) {
    return (
      <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <h3 className="text-base font-semibold text-zinc-950">Execution sequence</h3>
        <p className="mt-2 text-sm text-zinc-500">
          Apply a profile to see generated jobs and results.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
      <div className="border-b border-zinc-200 px-5 py-4">
        <h3 className="text-base font-semibold text-zinc-950">Execution sequence</h3>
        <p className="mt-1 text-sm text-zinc-500">{result.message}</p>
      </div>
      <div className="divide-y divide-zinc-100">
        {result.jobs.map((job, index) => (
          <div key={job.id} className="p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-zinc-950">Step {index + 1}</p>
                <p className="mt-1 break-all font-mono text-xs text-zinc-500">{job.command}</p>
              </div>
              <JobStatusBadge status={job.status} />
            </div>
            <pre className="mt-3 max-h-40 overflow-auto rounded-md bg-zinc-950 p-3 text-xs leading-5 text-zinc-50">
              {job.stdout?.trim() || job.stderr?.trim() || '(empty)'}
            </pre>
          </div>
        ))}
      </div>
    </section>
  );
}

function LoadingGrid() {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="h-56 animate-pulse rounded-lg bg-zinc-100" />
      ))}
    </div>
  );
}

function splitCsv(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeProfileSteps(steps: ProfileStep[]): ProfileStep[] {
  return steps.map((step, index) => {
    const kind = step.kind === 'script' ? 'command' : step.kind;
    const referenceId = step.reference_id || step.target || step.id || `${kind}-${index + 1}`;
    return {
      ...step,
      id: step.id || `${kind}-${referenceId}-${index + 1}`,
      kind,
      type: step.type ?? (kind === 'command' ? 'script' : kind),
      reference_id: referenceId,
      target: step.target ?? referenceId,
      name: step.name || referenceId,
      enabled: step.enabled ?? true,
      credential_ref: step.credential_ref ?? null,
    };
  });
}

````

## frontend/src/features/packages/api/packagesApi.ts

``typescript
import { apiClient } from '../../../lib/api/client';
import type { CreatePackageDefinitionPayload, PackageDefinition, UpdatePackageDefinitionPayload } from '../types/package';
import type { BulkExecutionResponse, Job } from '../../jobs/types/job';

export async function listPackageDefinitions(): Promise<PackageDefinition[]> {
  const response = await apiClient.get<PackageDefinition[]>('/packages');
  return response.data;
}

export async function createPackageDefinition(
  payload: CreatePackageDefinitionPayload,
): Promise<PackageDefinition> {
  const response = await apiClient.post<PackageDefinition>('/packages', payload);
  return response.data;
}

export async function updatePackageDefinition(
  packageId: string,
  payload: Partial<UpdatePackageDefinitionPayload>,
): Promise<PackageDefinition> {
  const response = await apiClient.put<PackageDefinition>(`/packages/${packageId}`, payload);
  return response.data;
}

export async function clonePackageDefinition(
  packageId: string,
  payload: { id: string; name?: string },
): Promise<PackageDefinition> {
  const response = await apiClient.post<PackageDefinition>(`/packages/${packageId}/clone`, payload);
  return response.data;
}

export async function resetPackageDefinition(packageId: string): Promise<PackageDefinition> {
  const response = await apiClient.post<PackageDefinition>(`/packages/${packageId}/reset`);
  return response.data;
}

export async function deletePackageDefinition(packageId: string): Promise<void> {
  await apiClient.delete(`/packages/${packageId}`);
}

export async function executePackageDefinition(
  packageId: string,
  targetServerId: string,
  variables: Record<string, string> = {},
  credentialRefs: Record<string, string> = {},
): Promise<Job> {
  const response = await apiClient.post<Job>(`/packages/${packageId}/execute`, {
    target_server_id: targetServerId,
    variables,
    credential_refs: credentialRefs,
  });
  return response.data;
}

export async function executePackageDefinitionBulk(
  packageId: string,
  targetServerIds: string[],
  variables: Record<string, string> = {},
  credentialRefs: Record<string, string> = {},
): Promise<BulkExecutionResponse> {
  const response = await apiClient.post<BulkExecutionResponse>('/packages/apply/bulk', {
    package_id: packageId,
    target_server_ids: targetServerIds,
    variables,
    credential_refs: credentialRefs,
  });
  return response.data;
}

````

## frontend/src/features/packages/types/package.ts

``typescript
export type PackageDefinition = {
  id: string;
  name: string;
  category: string;
  supported_os: string[];
  install_command: string;
  uninstall_command: string;
  validation_command: string;
  variables: TemplateVariable[];
  tags: string[];
  description: string;
  is_builtin: boolean;
  is_modified: boolean;
  base_version: string | null;
  source_template_id: string | null;
  modified_at: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type TemplateVariable = {
  name: string;
  description: string;
  default_value: string | null;
  required: boolean;
  sensitive: boolean;
  credential_type?: string | null;
};

export type CreatePackageDefinitionPayload = {
  id: string;
  name: string;
  category: string;
  supported_os: string[];
  install_command: string;
  uninstall_command: string;
  validation_command: string;
  variables: TemplateVariable[];
  tags: string[];
  description: string;
};

export type UpdatePackageDefinitionPayload = Omit<CreatePackageDefinitionPayload, 'id'>;

````

## frontend/src/features/packages/PackagesPage.tsx

``tsx
import { useEffect, useState } from 'react';

import { ContextDrawer } from '../../components/ContextDrawer';
import { PageHeader } from '../../components/layout/PageHeader';
import { PageActionButton } from '../../components/operations/OperationalComponents';
import {
  ExecutionVariablesModal,
  type ExecutionVariableValues,
} from '../../components/ExecutionVariablesModal';
import { VariableDefinitionEditor } from '../../components/VariableDefinitionEditor';
import { getApiErrorMessage } from '../../lib/api/client';
import { listCredentials } from '../credentials/api/credentialsApi';
import type { Credential } from '../credentials/types/credential';
import { listServers } from '../inventory/api/serversApi';
import { TargetSelector } from '../inventory/components/TargetSelector';
import { useTargetSelection } from '../inventory/hooks/useTargetSelection';
import type { Server } from '../inventory/types/server';
import {
  createPackageDefinition,
  clonePackageDefinition,
  deletePackageDefinition,
  executePackageDefinition,
  executePackageDefinitionBulk,
  listPackageDefinitions,
  resetPackageDefinition,
  updatePackageDefinition,
} from './api/packagesApi';
import type { CreatePackageDefinitionPayload, PackageDefinition } from './types/package';
import type { BulkExecutionResponse } from '../jobs/types/job';

type FormState = CreatePackageDefinitionPayload & {
  supported_os_text: string;
  tags_text: string;
};

const initialFormState: FormState = {
  id: '',
  name: '',
  category: '',
  supported_os: [],
  supported_os_text: 'ubuntu,debian',
  install_command: '',
  uninstall_command: '',
  validation_command: '',
  variables: [],
  tags: [],
  tags_text: '',
  description: '',
};

export function PackagesPage() {
  const [packages, setPackages] = useState<PackageDefinition[]>([]);
  const [servers, setServers] = useState<Server[]>([]);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [selectedServerId, setSelectedServerId] = useState('');
  const [selectedServerIds, setSelectedServerIds] = useState<string[]>([]);
  const [formState, setFormState] = useState<FormState>(initialFormState);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [executingPackageId, setExecutingPackageId] = useState<string | null>(null);
  const [pendingPackage, setPendingPackage] = useState<PackageDefinition | null>(null);
  const [bulkResult, setBulkResult] = useState<BulkExecutionResponse | null>(null);
  const [editingPackageId, setEditingPackageId] = useState<string | null>(null);
  const [isBuilderOpen, setIsBuilderOpen] = useState(false);
  const targetSelector = useTargetSelection('single');

  useEffect(() => {
    async function loadPackages() {
      setIsLoading(true);
      setError(null);

      try {
        const [nextPackages, nextServers, nextCredentials] = await Promise.all([
          listPackageDefinitions(),
          listServers(),
          listCredentials(),
        ]);
        setPackages(nextPackages);
        setServers(nextServers);
        setCredentials(nextCredentials);
        setSelectedServerId((current) => current || nextServers[0]?.id || '');
      } catch (caughtError) {
        setError(getApiErrorMessage(caughtError));
      } finally {
        setIsLoading(false);
      }
    }

    void loadPackages();
  }, []);

  function updateField(name: keyof FormState, value: string) {
    setFormState((current) => ({ ...current, [name]: value }));
    setError(null);
    setSuccess(null);
  }

  function startEdit(packageDefinition: PackageDefinition) {
    setIsBuilderOpen(true);
    setEditingPackageId(packageDefinition.id);
    setFormState({
      id: packageDefinition.id,
      name: packageDefinition.name,
      category: packageDefinition.category,
      supported_os: packageDefinition.supported_os,
      supported_os_text: packageDefinition.supported_os.join(','),
      install_command: packageDefinition.install_command,
      uninstall_command: packageDefinition.uninstall_command,
      validation_command: packageDefinition.validation_command,
      variables: packageDefinition.variables,
      tags: packageDefinition.tags,
      tags_text: packageDefinition.tags.join(','),
      description: packageDefinition.description,
    });
    setError(null);
    setSuccess(null);
  }

  function resetEditor() {
    setEditingPackageId(null);
    setFormState(initialFormState);
    setIsBuilderOpen(false);
  }

  async function handleCreatePackage() {
    if (!formState.id.trim() || !formState.name.trim() || !formState.install_command.trim()) {
      setError('Package id, name, and install command are required.');
      return;
    }

    setIsCreating(true);
    setError(null);
    setSuccess(null);

    try {
      const payload = {
        name: formState.name.trim(),
        category: formState.category.trim() || 'Custom',
        supported_os: splitCsv(formState.supported_os_text),
        install_command: formState.install_command.trim(),
        uninstall_command: formState.uninstall_command.trim(),
        validation_command: formState.validation_command.trim() || 'true',
        variables: formState.variables
          .filter((variable) => variable.name.trim())
          .map((variable) => ({
            ...variable,
            name: variable.name.trim(),
            description: variable.description.trim(),
          })),
        tags: splitCsv(formState.tags_text),
        description: formState.description.trim() || 'Custom package definition.',
      };
      if (editingPackageId) {
        const updated = await updatePackageDefinition(editingPackageId, payload);
        setPackages((current) => current.map((item) => (item.id === updated.id ? updated : item)));
        setSuccess(`Updated package ${updated.name}.`);
      } else {
        const created = await createPackageDefinition({ id: formState.id.trim(), ...payload });
        setPackages((current) => [...current, created]);
        setSuccess(`Created package ${created.name}.`);
      }
      resetEditor();
    } catch (caughtError) {
      setError(
        caughtError instanceof SyntaxError
          ? 'Variables must be valid JSON.'
          : getApiErrorMessage(caughtError),
      );
    } finally {
      setIsCreating(false);
    }
  }

  async function handleClonePackage(packageDefinition: PackageDefinition) {
    const id = window.prompt('Clone package as ID', `${packageDefinition.id}-copy`);
    if (!id) {
      return;
    }
    try {
      const cloned = await clonePackageDefinition(packageDefinition.id, {
        id: id.trim(),
        name: `${packageDefinition.name} Copy`,
      });
      setPackages((current) => [...current, cloned]);
      setSuccess(`Cloned package ${cloned.name}.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    }
  }

  async function handleResetPackage(packageDefinition: PackageDefinition) {
    const confirmed = window.confirm(
      `Restore ${packageDefinition.name} to the built-in default? Current edits will be discarded.`,
    );
    if (!confirmed) {
      return;
    }
    try {
      const restored = await resetPackageDefinition(packageDefinition.id);
      setPackages((current) => current.map((item) => (item.id === restored.id ? restored : item)));
      setSuccess(`Restored package ${restored.name} to default.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    }
  }

  async function handleDeletePackage(packageId: string) {
    const confirmed = window.confirm(`Delete package definition ${packageId}?`);
    if (!confirmed) {
      return;
    }

    try {
      await deletePackageDefinition(packageId);
      setPackages((current) =>
        current.filter((packageDefinition) => packageDefinition.id !== packageId),
      );
      setSuccess(`Deleted package ${packageId}.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    }
  }

  function handleExecutePackage(packageDefinition: PackageDefinition) {
    if (!selectedServerId && selectedServerIds.length === 0) {
      setError('Select one or more target hosts before running a package.');
      return;
    }
    setPendingPackage(packageDefinition);
    setError(null);
    setSuccess(null);
  }

  async function runPackage(
    packageDefinition: PackageDefinition,
    executionVariables: ExecutionVariableValues,
  ) {
    setExecutingPackageId(packageDefinition.id);
    setError(null);
    setSuccess(null);
    setBulkResult(null);

    try {
      if (selectedServerIds.length > 0) {
        const result = await executePackageDefinitionBulk(
          packageDefinition.id,
          selectedServerIds,
          executionVariables.variables,
          executionVariables.credential_refs,
        );
        setBulkResult(result);
        setSuccess(
          `Package ${packageDefinition.name}: ${result.success_count} succeeded, ${result.failure_count} failed.`,
        );
      } else {
        const job = await executePackageDefinition(
          packageDefinition.id,
          selectedServerId,
          executionVariables.variables,
          executionVariables.credential_refs,
        );
        setSuccess(`Started package ${packageDefinition.name}. Job status: ${job.status}.`);
      }
      setPendingPackage(null);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setExecutingPackageId(null);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Package Definitions"
        description="Reusable package standards that profiles can compose into orchestration workflows."
        actions={
          <PageActionButton tone="secondary" onClick={() => setIsBuilderOpen(true)}>
            Create package
          </PageActionButton>
        }
      />

      <TargetSelector
        servers={servers}
        eligibility="jobs"
        selection={{
          mode: targetSelector.selection.mode,
          selectedId: selectedServerId,
          selectedIds: selectedServerIds,
        }}
        filters={targetSelector.filters}
        title="Package targets"
        description="Install package definitions against one host or a filtered bulk selection."
        onFiltersChange={targetSelector.setFilters}
        onSelectionChange={(selection) => {
          targetSelector.setMode(selection.mode);
          setSelectedServerId(selection.selectedId);
          setSelectedServerIds(selection.selectedIds);
        }}
      />

      <ContextDrawer
        description="Create or tune package standards without losing the target and package list context."
        isOpen={isBuilderOpen}
        title={editingPackageId ? 'Edit Package' : 'Create Package'}
        width="xl"
        onClose={resetEditor}
      >
        <PackageBuilder
          formState={formState}
          editingPackageId={editingPackageId}
          isCreating={isCreating}
          onCreate={handleCreatePackage}
          onCancel={resetEditor}
          onFieldChange={updateField}
          onVariablesChange={(variables) => setFormState((current) => ({ ...current, variables }))}
        />
      </ContextDrawer>

      {success ? (
        <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
          {success}
        </p>
      ) : null}
      {error ? (
        <p className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          {error}
        </p>
      ) : null}
      {bulkResult ? <BulkResultPanel result={bulkResult} /> : null}
      {isLoading ? <LoadingGrid /> : null}
      {!isLoading && !error ? (
        <div className="grid gap-4 xl:grid-cols-2">
          {packages.map((packageDefinition) => (
            <PackageCard
              key={packageDefinition.id}
              isExecuting={executingPackageId === packageDefinition.id}
              packageDefinition={packageDefinition}
              onDelete={handleDeletePackage}
              onClone={handleClonePackage}
              onEdit={startEdit}
              onExecute={handleExecutePackage}
              onReset={handleResetPackage}
            />
          ))}
        </div>
      ) : null}
      <ExecutionVariablesModal
        credentials={credentials}
        isLoading={executingPackageId === pendingPackage?.id}
        isOpen={pendingPackage !== null}
        previewItems={
          pendingPackage
            ? [`Install ${pendingPackage.name}`, `Validate ${pendingPackage.name}`]
            : []
        }
        targetLabel={`${selectedServerIds.length || 1} host(s) selected`}
        title={pendingPackage ? `Run ${pendingPackage.name}` : 'Run package'}
        variables={pendingPackage?.variables ?? []}
        onCancel={() => setPendingPackage(null)}
        onConfirm={(values) => (pendingPackage ? runPackage(pendingPackage, values) : undefined)}
      />
    </div>
  );
}

function BulkResultPanel({ result }: { result: BulkExecutionResponse }) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-zinc-950">Bulk package result</h3>
      <p className="mt-1 text-sm text-zinc-500">
        {result.success_count} succeeded, {result.failure_count} failed
      </p>
      <div className="mt-4 divide-y divide-zinc-100 rounded-md border border-zinc-200">
        {result.results.map((item) => (
          <div key={item.target_server_id} className="px-3 py-2 text-sm">
            <span
              className={
                item.success ? 'font-semibold text-emerald-700' : 'font-semibold text-rose-700'
              }
            >
              {item.success ? 'Success' : 'Failed'}
            </span>
            <span className="ml-2 text-zinc-700">
              {item.target_hostname ?? item.target_server_id}
            </span>
            {item.error ? (
              <p className="mt-1 font-mono text-xs text-zinc-500">{item.error}</p>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}

function PackageBuilder({
  formState,
  editingPackageId,
  isCreating,
  onCreate,
  onCancel,
  onFieldChange,
  onVariablesChange,
}: {
  formState: FormState;
  editingPackageId: string | null;
  isCreating: boolean;
  onCreate: () => void;
  onCancel: () => void;
  onFieldChange: (name: keyof FormState, value: string) => void;
  onVariablesChange: (variables: FormState['variables']) => void;
}) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-zinc-950">
        {editingPackageId ? 'Edit package definition' : 'Add package definition'}
      </h3>
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <TextInput
          label="ID"
          name="id"
          placeholder="custom-agent"
          value={formState.id}
          onChange={onFieldChange}
        />
        <TextInput
          label="Name"
          name="name"
          placeholder="Custom Agent"
          value={formState.name}
          onChange={onFieldChange}
        />
        <TextInput
          label="Category"
          name="category"
          placeholder="Monitoring"
          value={formState.category}
          onChange={onFieldChange}
        />
        <TextInput
          label="Supported OS"
          name="supported_os_text"
          placeholder="ubuntu,debian"
          value={formState.supported_os_text}
          onChange={onFieldChange}
        />
        <TextInput
          label="Tags"
          name="tags_text"
          placeholder="monitoring,agent"
          value={formState.tags_text}
          onChange={onFieldChange}
        />
        <TextInput
          label="Description"
          name="description"
          placeholder="Installs a custom agent"
          value={formState.description}
          onChange={onFieldChange}
        />
        <TextArea
          label="Install command"
          name="install_command"
          value={formState.install_command}
          onChange={onFieldChange}
        />
        <TextArea
          label="Uninstall command"
          name="uninstall_command"
          value={formState.uninstall_command}
          onChange={onFieldChange}
        />
        <TextArea
          label="Validation command"
          name="validation_command"
          value={formState.validation_command}
          onChange={onFieldChange}
        />
        <VariableDefinitionEditor variables={formState.variables} onChange={onVariablesChange} />
      </div>
      <div className="mt-4 flex justify-end gap-2">
        {editingPackageId ? (
          <button
            className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50"
            type="button"
            onClick={onCancel}
          >
            Cancel
          </button>
        ) : null}
        <button
          className="rounded-md bg-zinc-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:bg-zinc-300"
          disabled={isCreating}
          type="button"
          onClick={onCreate}
        >
          {isCreating ? 'Saving' : editingPackageId ? 'Save package' : 'Create package'}
        </button>
      </div>
    </section>
  );
}

function PackageCard({
  packageDefinition,
  isExecuting,
  onDelete,
  onClone,
  onEdit,
  onExecute,
  onReset,
}: {
  packageDefinition: PackageDefinition;
  isExecuting: boolean;
  onDelete: (packageId: string) => void;
  onClone: (packageDefinition: PackageDefinition) => void;
  onEdit: (packageDefinition: PackageDefinition) => void;
  onExecute: (packageDefinition: PackageDefinition) => void;
  onReset: (packageDefinition: PackageDefinition) => void;
}) {
  return (
    <article className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm ring-1 ring-transparent transition hover:border-zinc-300 hover:shadow-md">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h3 className="text-lg font-semibold text-zinc-950">{packageDefinition.name}</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-600">
            {packageDefinition.description}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="inline-flex w-fit rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-700 ring-1 ring-inset ring-zinc-200">
            {packageDefinition.category}
          </span>
          <span className="inline-flex w-fit rounded-full bg-zinc-50 px-2.5 py-1 text-xs font-medium text-zinc-600 ring-1 ring-inset ring-zinc-200">
            {packageDefinition.is_builtin ? 'Built-in' : 'Custom'}
          </span>
          {packageDefinition.is_modified ? <Badge label="Modified" /> : null}
          {packageDefinition.source_template_id && !packageDefinition.is_builtin ? (
            <Badge label="Cloned" />
          ) : null}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {packageDefinition.tags.map((tag) => (
          <span
            key={tag}
            className="rounded-full bg-zinc-50 px-2.5 py-1 text-xs text-zinc-600 ring-1 ring-zinc-200"
          >
            {tag}
          </span>
        ))}
      </div>

      <dl className="mt-5 space-y-4 rounded-md border border-zinc-200 bg-zinc-50 p-3">
        <CommandBlock label="Install" value={packageDefinition.install_command} />
        {packageDefinition.uninstall_command ? (
          <CommandBlock label="Uninstall" value={packageDefinition.uninstall_command} />
        ) : null}
        <CommandBlock label="Validate" value={packageDefinition.validation_command} />
      </dl>
      {packageDefinition.variables.length ? (
        <div className="mt-4 rounded-md border border-zinc-200 bg-white p-3">
          <p className="text-xs font-semibold uppercase text-zinc-500">Variables</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {packageDefinition.variables.map((variable) => (
              <span
                key={variable.name}
                className="rounded bg-zinc-100 px-2 py-1 font-mono text-xs text-zinc-700"
              >
                {variable.name}
                {variable.required ? ' *' : ''}
                {variable.sensitive ? ' sensitive' : ''}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      <p className="mt-4 text-xs text-zinc-500">
        Supported OS: {packageDefinition.supported_os.join(', ')}
      </p>

      <div className="mt-5 flex flex-wrap justify-end gap-2">
        <button
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50"
          type="button"
          onClick={() => onClone(packageDefinition)}
        >
          Clone
        </button>
        <button
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50"
          type="button"
          onClick={() => onEdit(packageDefinition)}
        >
          Edit
        </button>
        {packageDefinition.is_builtin && packageDefinition.is_modified ? (
          <button
            className="rounded-md border border-amber-300 px-3 py-2 text-sm font-semibold text-amber-700 transition hover:bg-amber-50"
            type="button"
            onClick={() => onReset(packageDefinition)}
          >
            Restore default
          </button>
        ) : null}
        {!packageDefinition.is_builtin ? (
          <button
            className="rounded-md border border-rose-300 px-3 py-2 text-sm font-semibold text-rose-700 transition hover:bg-rose-50"
            type="button"
            onClick={() => onDelete(packageDefinition.id)}
          >
            Delete
          </button>
        ) : null}
        <button
          className="rounded-md bg-zinc-950 px-3 py-2 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:bg-zinc-300"
          disabled={isExecuting}
          type="button"
          onClick={() => onExecute(packageDefinition)}
        >
          {isExecuting ? 'Running' : 'Run package'}
        </button>
      </div>
    </article>
  );
}

function Badge({ label }: { label: string }) {
  return (
    <span className="inline-flex w-fit rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700 ring-1 ring-inset ring-amber-200">
      {label}
    </span>
  );
}

function TextInput({
  label,
  name,
  value,
  placeholder,
  onChange,
}: {
  label: string;
  name: keyof FormState;
  value: string;
  placeholder: string;
  onChange: (name: keyof FormState, value: string) => void;
}) {
  return (
    <label className="text-sm font-medium text-zinc-700">
      {label}
      <input
        className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10"
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(name, event.target.value)}
      />
    </label>
  );
}

function TextArea({
  label,
  name,
  value,
  onChange,
}: {
  label: string;
  name: keyof FormState;
  value: string;
  onChange: (name: keyof FormState, value: string) => void;
}) {
  return (
    <label className="text-sm font-medium text-zinc-700 xl:col-span-3">
      {label}
      <textarea
        className="mt-1 min-h-24 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 font-mono text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10"
        value={value}
        onChange={(event) => onChange(name, event.target.value)}
      />
    </label>
  );
}

function CommandBlock({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-normal text-zinc-500">{label}</dt>
      <dd className="mt-1 overflow-auto rounded-md bg-zinc-950 p-3 font-mono text-xs leading-5 text-zinc-50">
        {value}
      </dd>
    </div>
  );
}

function splitCsv(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function LoadingGrid() {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="h-64 animate-pulse rounded-lg bg-zinc-100" />
      ))}
    </div>
  );
}

````

