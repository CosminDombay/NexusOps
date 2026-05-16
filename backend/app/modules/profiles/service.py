from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from backend.app.common.variables import VariableResolutionError, VariableResolutionService
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
    ProfileBulkApplyRead,
    ProfileBulkApplyRequest,
    ProfileBulkHostResult,
    ProfileApplyRequest,
    ProfileCloneRequest,
)


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
    ) -> None:
        self.job_service = job_service
        self.repository = repository
        self.package_repository = package_repository
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
        for step in profile.steps:
            if getattr(step, "enabled", True) is False:
                continue
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

        success_count = sum(1 for result in results if result.success)
        return ProfileBulkApplyRead(
            profile_id=payload.profile_id,
            success_count=success_count,
            failure_count=len(results) - success_count,
            results=results,
        )

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
