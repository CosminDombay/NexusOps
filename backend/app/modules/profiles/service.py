from backend.app.modules.jobs.actions import get_action
from backend.app.modules.jobs.schemas import JobExecuteRequest
from backend.app.modules.jobs.service import JobService
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
    ProfileApplyRequest,
)

from sqlalchemy.exc import IntegrityError


class ProfileNotFoundError(Exception):
    """Raised when a profile template cannot be found."""


class ProfileStepResolutionError(Exception):
    """Raised when a profile step references an unknown action/package."""


class ProfileConflictError(Exception):
    """Raised when a profile slug already exists."""


class BuiltinProfileError(Exception):
    """Raised when trying to mutate a built-in profile."""


class ProfileService:
    """Application service for reusable infrastructure profile orchestration."""

    def __init__(
        self,
        *,
        job_service: JobService,
        repository: InfrastructureProfileRepository | None = None,
        package_repository: PackageDefinitionRepository | None = None,
    ) -> None:
        self.job_service = job_service
        self.repository = repository
        self.package_repository = package_repository

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
            steps=[step.model_dump() for step in payload.steps],
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

        if get_profile(profile_id):
            raise BuiltinProfileError("Built-in profiles cannot be edited")

        record = await self.repository.get_by_slug(profile_id)
        if record is None:
            raise ProfileNotFoundError("Profile not found")

        update_data = payload.model_dump(exclude_unset=True)
        if "steps" in update_data and update_data["steps"] is not None:
            update_data["steps"] = [
                step.model_dump() if hasattr(step, "model_dump") else step
                for step in payload.steps or []
            ]

        for key, value in update_data.items():
            setattr(record, key, value)

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

    async def apply_profile(self, profile_id: str, payload: ProfileApplyRequest) -> ProfileApplyRead:
        profile = await self.get_profile(profile_id)

        jobs = []
        status = "success"
        for step in profile.steps:
            command = await self._resolve_step_command(step.kind, step.reference_id)
            job = await self.job_service.execute(
                JobExecuteRequest(
                    target_server_id=payload.target_server_id,
                    operation_type=f"profile:{profile.id}:{step.id}",
                    command=command,
                )
            )
            jobs.append(job)
            if job.status == "failed" and payload.stop_on_failure:
                status = "failed"
                break

        if any(job.status == "failed" for job in jobs) and status != "failed":
            status = "completed_with_failures"

        return ProfileApplyRead(
            profile_id=profile.id,
            target_server_id=payload.target_server_id,
            status=status,
            jobs=jobs,
            message=f"Profile {profile.name} executed {len(jobs)} step(s).",
        )

    async def _resolve_step_command(self, kind: str, reference_id: str) -> str:
        if kind == "action":
            action = get_action(reference_id)
            if action is None:
                raise ProfileStepResolutionError(f"Unknown action reference: {reference_id}")
            return action.command

        if kind == "package":
            package = get_package_definition(reference_id)
            if package is not None:
                return f"{package.install_command} && {package.validation_command}"

            if self.package_repository is None:
                raise ProfileStepResolutionError(f"Unknown package reference: {reference_id}")

            package_service = PackageAutomationService(repository=self.package_repository)
            try:
                package_read = await package_service.get_definition(reference_id)
            except Exception as exc:
                raise ProfileStepResolutionError(
                    f"Unknown package reference: {reference_id}"
                ) from exc
            return f"{package_read.install_command} && {package_read.validation_command}"

        raise ProfileStepResolutionError(f"Unsupported profile step kind: {kind}")

    @staticmethod
    def _builtin_to_read(profile: InfrastructureProfile) -> InfrastructureProfileRead:
        return InfrastructureProfileRead(
            id=profile.id,
            name=profile.name,
            category=profile.category,
            description=profile.description,
            tags=profile.tags,
            steps=[step.__dict__ for step in profile.steps],
            is_builtin=True,
        )

    @staticmethod
    def _record_to_read(record: InfrastructureProfileRecord) -> InfrastructureProfileRead:
        return InfrastructureProfileRead(
            id=record.slug,
            name=record.name,
            category=record.category,
            description=record.description,
            tags=record.tags,
            steps=record.steps,
            is_builtin=record.is_builtin,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
