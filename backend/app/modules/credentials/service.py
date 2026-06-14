from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.app.modules.automations.models import Automation
from backend.app.modules.credentials.encryption_service import EncryptionService
from backend.app.modules.credentials.models import Credential, CredentialUsage
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.schemas import (
    CredentialCreate,
    CredentialReferenceRead,
    CredentialRead,
    CredentialUpdate,
    CredentialUsageRead,
    ResolvedCredential,
)
from backend.app.modules.deployments.models import Deployment
from backend.app.modules.identity.models import LinuxUser
from backend.app.modules.integrations.models import Integration
from backend.app.modules.inventory.models import Server
from backend.app.modules.profiles.models import InfrastructureProfileRecord
from backend.app.modules.variables.models import Variable


class CredentialConflictError(Exception):
    """Raised when a credential name is already in use."""


class CredentialNotFoundError(Exception):
    """Raised when a credential cannot be found."""


class CredentialInUseError(Exception):
    """Raised when a credential is still referenced by an orchestration record."""


class CredentialService:
    def __init__(
        self,
        *,
        repository: CredentialRepository,
        encryption_service: EncryptionService | None = None,
    ) -> None:
        self.repository = repository
        self.encryption_service = encryption_service or EncryptionService()

    async def list_credentials(self, *, include_deleted: bool = False, only_deleted: bool = False) -> list[CredentialRead]:
        credentials = await self.repository.list(include_deleted=include_deleted, only_deleted=only_deleted)
        return [await self._to_read(credential) for credential in credentials]

    async def create_credential(self, payload: CredentialCreate) -> CredentialRead:
        if await self.repository.get_by_name(payload.name, include_deleted=True):
            raise CredentialConflictError("Credential name already exists")

        credential = Credential(
            name=payload.name,
            description=payload.description,
            credential_type=payload.credential_type,
            username=payload.username,
            encrypted_secret=self.encryption_service.encrypt_value(payload.secret),
            private_key=self.encryption_service.encrypt_value(payload.private_key),
            passphrase=self.encryption_service.encrypt_value(payload.passphrase),
            tags=payload.tags,
            scope=payload.scope,
        )
        try:
            credential = await self.repository.create(credential)
            await self.repository.session.commit()
        except IntegrityError as exc:
            await self.repository.session.rollback()
            raise CredentialConflictError("Credential name already exists") from exc
        return await self._to_read(credential)

    async def update_credential(self, credential_id: UUID, payload: CredentialUpdate) -> CredentialRead:
        credential = await self.repository.get_by_id(credential_id)
        if credential is None:
            raise CredentialNotFoundError("Credential not found")

        update_data = payload.model_dump(exclude_unset=True)
        if "name" in update_data and update_data["name"] != credential.name:
            existing = await self.repository.get_by_name(update_data["name"], include_deleted=True)
            if existing and existing.id != credential.id:
                raise CredentialConflictError("Credential name already exists")

        secret = update_data.pop("secret", None)
        private_key = update_data.pop("private_key", None)
        passphrase = update_data.pop("passphrase", None)
        if secret is not None:
            credential.encrypted_secret = self.encryption_service.encrypt_value(secret)
        if private_key is not None:
            credential.private_key = self.encryption_service.encrypt_value(private_key)
        if passphrase is not None:
            credential.passphrase = self.encryption_service.encrypt_value(passphrase)

        for key, value in update_data.items():
            setattr(credential, key, value)

        try:
            await self.repository.session.commit()
            await self.repository.session.refresh(credential)
        except IntegrityError as exc:
            await self.repository.session.rollback()
            raise CredentialConflictError("Credential name already exists") from exc
        return await self._to_read(credential)

    async def delete_credential(self, credential_id: UUID, *, deleted_by: str | None = None, reason: str | None = None) -> CredentialRead:
        credential = await self.repository.get_by_id(credential_id)
        if credential is None:
            raise CredentialNotFoundError("Credential not found")
        credential.deleted_at = datetime.now(UTC)
        credential.deleted_by = deleted_by
        credential.delete_reason = reason
        await self.repository.session.commit()
        await self.repository.session.refresh(credential)
        return await self._to_read(credential)

    async def restore_credential(self, credential_id: UUID) -> CredentialRead:
        credential = await self.repository.get_by_id(credential_id, include_deleted=True)
        if credential is None:
            raise CredentialNotFoundError("Credential not found")
        credential.deleted_at = None
        credential.deleted_by = None
        credential.delete_reason = None
        await self.repository.session.commit()
        await self.repository.session.refresh(credential)
        return await self._to_read(credential)

    async def purge_credential(self, credential_id: UUID) -> None:
        credential = await self.repository.get_by_id(credential_id, include_deleted=True)
        if credential is None:
            raise CredentialNotFoundError("Credential not found")
        if credential.deleted_at is None:
            raise CredentialInUseError("Move credential to Trash before permanent deletion.")
        references = await self.find_references(credential)
        if references:
            raise CredentialInUseError(
                f"Credential is still referenced by {len(references)} record(s). "
                "Clear or change those references before permanent deletion."
            )
        await self.repository.delete(credential)
        await self.repository.session.commit()

    async def usage(self, credential_id: UUID) -> CredentialUsageRead:
        credential = await self.repository.get_by_id(credential_id, include_deleted=True)
        if credential is None:
            raise CredentialNotFoundError("Credential not found")
        return CredentialUsageRead(credential_id=credential.id, references=await self.find_references(credential))

    async def resolve_credential(self, credential_id_or_name: UUID | str) -> ResolvedCredential:
        credential = None
        if isinstance(credential_id_or_name, UUID):
            credential = await self.repository.get_by_id(credential_id_or_name)
        else:
            try:
                credential = await self.repository.get_by_id(UUID(credential_id_or_name))
            except ValueError:
                credential = await self.repository.get_by_name(credential_id_or_name)

        if credential is None:
            raise CredentialNotFoundError("Credential not found")

        return ResolvedCredential(
            id=credential.id,
            name=credential.name,
            credential_type=credential.credential_type,
            username=credential.username,
            secret=self.encryption_service.decrypt_value(credential.encrypted_secret),
            private_key=self.encryption_service.decrypt_value(credential.private_key),
            passphrase=self.encryption_service.decrypt_value(credential.passphrase),
        )

    async def _to_read(self, credential: Credential) -> CredentialRead:
        return CredentialRead(
            id=credential.id,
            name=credential.name,
            description=credential.description,
            credential_type=credential.credential_type,
            username=credential.username,
            masked_secret="********" if credential.encrypted_secret or credential.private_key else "",
            tags=credential.tags,
            scope=credential.scope,
            deleted_at=credential.deleted_at,
            deleted_by=credential.deleted_by,
            delete_reason=credential.delete_reason,
            reference_count=len(await self.find_references(credential)),
            created_at=credential.created_at,
            updated_at=credential.updated_at,
        )

    async def find_references(self, credential: Credential) -> list[CredentialReferenceRead]:
        credential_id = credential.id
        references: list[CredentialReferenceRead] = []

        servers = await self._scalars(select(Server).where(Server.credential_id == credential_id))
        references.extend(
            CredentialReferenceRead(
                reference_type="inventory_server",
                reference_id=str(server.id),
                name=server.hostname,
                field="credential_id",
                detail="Inventory SSH credential",
            )
            for server in servers
        )

        variables = await self._scalars(select(Variable).where(Variable.credential_id == credential_id))
        references.extend(
            CredentialReferenceRead(
                reference_type="variable",
                reference_id=str(variable.id),
                name=variable.key,
                field="credential_id",
                detail="Secret variable credential",
            )
            for variable in variables
        )

        for deployment in await self._scalars(select(Deployment)):
            if self._matches_ref(deployment.execution_credential_ref, credential):
                references.append(
                    CredentialReferenceRead(
                        reference_type="deployment",
                        reference_id=str(deployment.id),
                        name=deployment.name,
                        field="execution_credential_ref",
                        detail="Deployment execution/sudo credential",
                    )
                )
            references.extend(
                self._json_credential_refs(
                    deployment.credential_refs,
                    credential,
                    reference_type="deployment",
                    reference_id=str(deployment.id),
                    name=deployment.name,
                    field_prefix="credential_refs",
                )
            )

        for automation in await self._scalars(select(Automation)):
            if self._matches_ref(automation.execution_credential_ref, credential):
                references.append(
                    CredentialReferenceRead(
                        reference_type="automation",
                        reference_id=str(automation.id),
                        name=automation.name,
                        field="execution_credential_ref",
                        detail="Automation execution/sudo credential",
                    )
                )
            references.extend(
                self._json_credential_refs(
                    automation.credential_refs,
                    credential,
                    reference_type="automation",
                    reference_id=str(automation.id),
                    name=automation.name,
                    field_prefix="credential_refs",
                )
            )

        for integration in await self._scalars(select(Integration)):
            references.extend(
                self._json_credential_refs(
                    integration.credential_refs,
                    credential,
                    reference_type="integration",
                    reference_id=str(integration.id),
                    name=integration.name,
                    field_prefix="credential_refs",
                )
            )

        users = await self._scalars(select(LinuxUser))
        references.extend(
            CredentialReferenceRead(
                reference_type="identity_user",
                reference_id=str(user.id),
                name=user.username,
                field="password_credential_ref",
                detail="Linux account password credential",
            )
            for user in users
            if self._matches_ref(user.password_credential_ref, credential)
        )

        profiles = await self._scalars(select(InfrastructureProfileRecord))
        for profile in profiles:
            for index, step in enumerate(profile.steps or []):
                if self._matches_ref((step or {}).get("credential_ref"), credential):
                    references.append(
                        CredentialReferenceRead(
                            reference_type="profile",
                            reference_id=str(profile.id),
                            name=profile.name,
                            field=f"steps[{index}].credential_ref",
                            detail="Profile step execution credential",
                        )
                    )

        usages = await self._scalars(select(CredentialUsage).where(CredentialUsage.credential_id == credential_id))
        references.extend(
            CredentialReferenceRead(
                reference_type=usage.used_by_type,
                reference_id=usage.used_by_id,
                name=usage.used_by_id,
                field="credential_usages",
                detail=usage.purpose,
            )
            for usage in usages
        )

        return references

    async def _scalars(self, query):
        result = await self.repository.session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    def _matches_ref(value: object, credential: Credential) -> bool:
        if value is None:
            return False
        clean = str(value).strip()
        return clean in {str(credential.id), credential.name}

    def _json_credential_refs(
        self,
        credential_refs: dict | None,
        credential: Credential,
        *,
        reference_type: str,
        reference_id: str,
        name: str,
        field_prefix: str,
    ) -> list[CredentialReferenceRead]:
        references: list[CredentialReferenceRead] = []
        for key, value in (credential_refs or {}).items():
            if self._matches_ref(value, credential):
                references.append(
                    CredentialReferenceRead(
                        reference_type=reference_type,
                        reference_id=reference_id,
                        name=name,
                        field=f"{field_prefix}.{key}",
                        detail=f"Credential-backed value for {key}",
                    )
                )
        return references
