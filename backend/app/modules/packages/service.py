from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from backend.app.common.import_export import ExportFormat, ImportExportError, parse_document, render_document
from backend.app.common.variables import VariableResolutionError, VariableResolutionService
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.jobs.schemas import BulkExecutionRead, JobBulkExecuteRequest, JobExecuteRequest, JobRead
from backend.app.modules.jobs.service import JobService
from backend.app.modules.orchestration.security import SafeCommandBuilder
from backend.app.modules.packages.definitions import (
    PackageDefinition,
    get_package_definition,
    list_package_definitions,
)
from backend.app.modules.packages.models import PackageDefinitionRecord
from backend.app.modules.packages.repository import PackageDefinitionRepository
from backend.app.modules.packages.schemas import (
    PackageDefinitionCreate,
    PackageDefinitionExportRead,
    PackageDefinitionImportRead,
    PackageDefinitionImportRequest,
    PackageDefinitionRead,
    PackageDefinitionUpdate,
    PackageBulkApplyRequest,
    PackageCloneRequest,
    PackageExecuteRequest,
    VALID_CREDENTIAL_TYPES,
)


class PackageDefinitionNotFoundError(Exception):
    """Raised when a package definition cannot be found."""


class PackageDefinitionConflictError(Exception):
    """Raised when a package definition slug already exists."""


class BuiltinPackageDefinitionError(Exception):
    """Raised when trying to mutate a built-in package definition."""


class PackageDefinitionImportError(Exception):
    """Raised when a package import document is invalid."""


SYSTEM_TEMPLATE_VERSION = "2026.05.16"
EXPORT_VERSION = 1


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
        self.command_builder = SafeCommandBuilder(self.variable_service)

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

        if get_package_definition(payload.id) or await self.repository.get_by_slug(payload.id, include_deleted=True):
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

    async def export_definition(
        self,
        package_id: str,
        document_format: ExportFormat = "json",
    ) -> PackageDefinitionExportRead:
        definition = await self.get_definition(package_id)
        payload = {
            "kind": "nexusops.package",
            "version": EXPORT_VERSION,
            "package": self._definition_to_create_payload(definition),
        }
        extension = "yaml" if document_format == "yaml" else "json"
        return PackageDefinitionExportRead(
            filename=f"{definition.id}.package.{extension}",
            format=document_format,
            content=render_document(payload, document_format),
        )

    async def import_definition(self, payload: PackageDefinitionImportRequest) -> PackageDefinitionImportRead:
        try:
            document = parse_document(payload.content, payload.format)
        except ImportExportError as exc:
            raise PackageDefinitionImportError(str(exc)) from exc

        if document.get("kind") != "nexusops.package":
            raise PackageDefinitionImportError("Import document kind must be nexusops.package")
        if document.get("version") != EXPORT_VERSION:
            raise PackageDefinitionImportError(f"Unsupported package import version: {document.get('version')}")
        if not isinstance(document.get("package"), dict):
            raise PackageDefinitionImportError("Import document must contain a package object")

        try:
            create_payload = PackageDefinitionCreate.model_validate(document["package"])
        except ValueError as exc:
            raise PackageDefinitionImportError("Package import document failed validation") from exc

        status = "created"
        if await self._definition_exists(create_payload.id):
            if payload.strategy == "create":
                raise PackageDefinitionConflictError("Package definition already exists")
            create_payload = create_payload.model_copy(
                update={
                    "id": await self._next_available_import_id(create_payload.id, payload.clone_suffix),
                    "name": f"{create_payload.name} Import",
                }
            )
            status = "cloned"

        package = await self.create_definition(create_payload)
        return PackageDefinitionImportRead(package=package, status=status, warnings=[])

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

        record.deleted_at = datetime.now(UTC)
        await self.repository.session.commit()

    async def clone_definition(self, package_id: str, payload: PackageCloneRequest) -> PackageDefinitionRead:
        if self.repository is None:
            raise RuntimeError("Package definition repository is required")
        if get_package_definition(payload.id) or await self.repository.get_by_slug(payload.id, include_deleted=True):
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

    async def _definition_exists(self, package_id: str) -> bool:
        if get_package_definition(package_id):
            return True
        if self.repository is None:
            return False
        return await self.repository.get_by_slug(package_id, include_deleted=True) is not None

    async def _next_available_import_id(self, package_id: str, suffix: str) -> str:
        base = f"{package_id}-{suffix}"
        candidate = base
        counter = 2
        while await self._definition_exists(candidate):
            candidate = f"{base}-{counter}"
            counter += 1
        return candidate

    async def execute_definition(self, package_id: str, payload: PackageExecuteRequest) -> JobRead:
        if self.job_service is None:
            raise RuntimeError("Job service is required")

        definition = await self.get_definition(package_id)
        command, redacted_command = await self._resolve_definition_commands(
            definition,
            payload.variables,
            payload.credential_refs,
            operation=payload.operation,
        )
        return await self.job_service.execute(
            JobExecuteRequest(
                target_server_id=payload.target_server_id,
                operation_type=f"package:{payload.operation}:{definition.id}",
                command=command,
                redacted_command=redacted_command,
                credential_ref=payload.execution_credential_ref,
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
            operation=payload.operation,
        )
        return await self.job_service.execute_bulk(
            JobBulkExecuteRequest(
                target_server_ids=payload.target_server_ids,
                operation_type=f"package:{payload.operation}:{definition.id}",
                command=command,
                redacted_command=redacted_command,
                credential_ref=payload.execution_credential_ref,
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
            variables=PackageAutomationService._sanitize_variable_definitions(record.variables),
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

    @staticmethod
    def _definition_to_create_payload(definition: PackageDefinitionRead) -> dict:
        return {
            "id": definition.id,
            "name": definition.name,
            "category": definition.category,
            "supported_os": definition.supported_os,
            "install_command": definition.install_command,
            "uninstall_command": definition.uninstall_command,
            "validation_command": definition.validation_command,
            "variables": [variable.model_dump() for variable in definition.variables],
            "tags": definition.tags,
            "description": definition.description,
        }

    @staticmethod
    def _sanitize_variable_definitions(variables: list[dict]) -> list[dict]:
        sanitized = []
        for variable in variables:
            item = dict(variable)
            credential_type = item.get("credential_type")
            if credential_type and credential_type not in VALID_CREDENTIAL_TYPES:
                item["credential_type"] = None
            if item.get("credential_ref"):
                item["sensitive"] = True
            sanitized.append(item)
        return sanitized

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
            install = self.command_builder.resolve_template(
                definition.install_command,
                definitions=[variable.model_dump() for variable in definition.variables],
                variables=variables,
                source=f"package:{definition.id}:install",
            )
            validation = self.command_builder.resolve_template(
                definition.validation_command,
                definitions=[variable.model_dump() for variable in definition.variables],
                variables=variables,
                source=f"package:{definition.id}:validation",
            )
        except VariableResolutionError:
            raise
        return f"{install} && {validation}"

    async def _resolve_definition_commands(
        self,
        definition: PackageDefinitionRead,
        variables: dict[str, str],
        credential_refs: dict[str, str],
        *,
        operation: str = "install",
    ) -> tuple[str, str]:
        definitions = [variable.model_dump() for variable in definition.variables]
        secret_values = await self._resolve_secret_variables(definitions, variables, credential_refs)
        safe_variables = self._without_sensitive_plaintext(definitions, variables, credential_refs)
        runtime_variables = {**safe_variables, **secret_values}
        redacted_variables = {**safe_variables, **{name: "********" for name in secret_values}}

        command_template = definition.install_command if operation == "install" else definition.uninstall_command
        if operation == "uninstall" and not command_template.strip():
            raise VariableResolutionError(f"Package {definition.id} has no uninstall command configured")

        command = self.command_builder.resolve_template(
            command_template,
            definitions=definitions,
            variables=runtime_variables,
            source=f"package:{definition.id}:{operation}",
        )
        redacted_command = self.command_builder.resolve_template(
            command_template,
            definitions=definitions,
            variables=redacted_variables,
            source=f"package:{definition.id}:{operation}:redacted",
        )
        if operation == "uninstall":
            return command, redacted_command

        validation = self.command_builder.resolve_template(
            definition.validation_command,
            definitions=definitions,
            variables=runtime_variables,
            source=f"package:{definition.id}:validation",
        )
        redacted_validation = self.command_builder.resolve_template(
            definition.validation_command,
            definitions=definitions,
            variables=redacted_variables,
            source=f"package:{definition.id}:validation:redacted",
        )
        return f"{command} && {validation}", f"{redacted_command} && {redacted_validation}"

    async def _resolve_secret_variables(
        self,
        definitions: list[dict],
        variables: dict[str, str],
        credential_refs: dict[str, str],
    ) -> dict[str, str]:
        secret_values: dict[str, str] = {}
        definition_by_name = {
            str(item["name"]): item
            for item in definitions
            if item.get("name")
        }
        for name, definition in definition_by_name.items():
            credential_ref = credential_refs.get(name) or definition.get("credential_ref")
            if not credential_ref:
                if definition.get("sensitive") and variables.get(name):
                    secret_values[name] = variables[name]
                    continue
                if definition.get("required") and definition.get("sensitive"):
                    raise VariableResolutionError(
                        f"Sensitive variable {name} requires a credential reference or sensitive runtime value"
                    )
                continue
            if self.credential_service is None:
                raise VariableResolutionError("Credential service is required for credential-backed package variables")
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
        credential_backed_names = {name for name, value in credential_refs.items() if value}
        credential_backed_names.update(
            str(item["name"]) for item in definitions if item.get("name") and item.get("credential_ref")
        )
        excluded_names = sensitive_names | credential_backed_names
        return {name: value for name, value in variables.items() if name not in excluded_names}
