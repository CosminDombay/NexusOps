from sqlalchemy.exc import IntegrityError

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
    PackageExecuteRequest,
)


class PackageDefinitionNotFoundError(Exception):
    """Raised when a package definition cannot be found."""


class PackageDefinitionConflictError(Exception):
    """Raised when a package definition slug already exists."""


class BuiltinPackageDefinitionError(Exception):
    """Raised when trying to mutate a built-in package definition."""


class PackageAutomationService:
    """Application service for reusable package definitions."""

    def __init__(
        self,
        *,
        repository: PackageDefinitionRepository | None = None,
        job_service: JobService | None = None,
    ) -> None:
        self.repository = repository
        self.job_service = job_service

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
            validation_command=payload.validation_command,
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

        if get_package_definition(package_id):
            raise BuiltinPackageDefinitionError("Built-in package definitions cannot be edited")

        record = await self.repository.get_by_slug(package_id)
        if record is None:
            raise PackageDefinitionNotFoundError("Package definition not found")

        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(record, key, value)

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

    async def execute_definition(self, package_id: str, payload: PackageExecuteRequest) -> JobRead:
        if self.job_service is None:
            raise RuntimeError("Job service is required")

        definition = await self.get_definition(package_id)
        command = f"{definition.install_command} && {definition.validation_command}"
        return await self.job_service.execute(
            JobExecuteRequest(
                target_server_id=payload.target_server_id,
                operation_type=f"package:{definition.id}",
                command=command,
            )
        )

    async def execute_definition_bulk(self, payload: PackageBulkApplyRequest) -> BulkExecutionRead:
        if self.job_service is None:
            raise RuntimeError("Job service is required")

        definition = await self.get_definition(payload.package_id)
        command = f"{definition.install_command} && {definition.validation_command}"
        return await self.job_service.execute_bulk(
            JobBulkExecuteRequest(
                target_server_ids=payload.target_server_ids,
                operation_type=f"package:{definition.id}",
                command=command,
            )
        )

    @staticmethod
    def _builtin_to_read(definition: PackageDefinition) -> PackageDefinitionRead:
        return PackageDefinitionRead(**definition.__dict__, is_builtin=True)

    @staticmethod
    def _record_to_read(record: PackageDefinitionRecord) -> PackageDefinitionRead:
        return PackageDefinitionRead(
            id=record.slug,
            name=record.name,
            category=record.category,
            supported_os=record.supported_os,
            install_command=record.install_command,
            validation_command=record.validation_command,
            tags=record.tags,
            description=record.description,
            is_builtin=record.is_builtin,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
