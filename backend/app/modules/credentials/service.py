from uuid import UUID

from sqlalchemy.exc import IntegrityError

from backend.app.modules.credentials.encryption_service import EncryptionService
from backend.app.modules.credentials.models import Credential
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.schemas import (
    CredentialCreate,
    CredentialRead,
    CredentialUpdate,
    ResolvedCredential,
)


class CredentialConflictError(Exception):
    """Raised when a credential name is already in use."""


class CredentialNotFoundError(Exception):
    """Raised when a credential cannot be found."""


class CredentialService:
    def __init__(
        self,
        *,
        repository: CredentialRepository,
        encryption_service: EncryptionService | None = None,
    ) -> None:
        self.repository = repository
        self.encryption_service = encryption_service or EncryptionService()

    async def list_credentials(self) -> list[CredentialRead]:
        return [self._to_read(credential) for credential in await self.repository.list()]

    async def create_credential(self, payload: CredentialCreate) -> CredentialRead:
        if await self.repository.get_by_name(payload.name):
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
        return self._to_read(credential)

    async def update_credential(self, credential_id: UUID, payload: CredentialUpdate) -> CredentialRead:
        credential = await self.repository.get_by_id(credential_id)
        if credential is None:
            raise CredentialNotFoundError("Credential not found")

        update_data = payload.model_dump(exclude_unset=True)
        if "name" in update_data and update_data["name"] != credential.name:
            existing = await self.repository.get_by_name(update_data["name"])
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
        return self._to_read(credential)

    async def delete_credential(self, credential_id: UUID) -> None:
        credential = await self.repository.get_by_id(credential_id)
        if credential is None:
            raise CredentialNotFoundError("Credential not found")
        await self.repository.delete(credential)
        await self.repository.session.commit()

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

    @staticmethod
    def _to_read(credential: Credential) -> CredentialRead:
        return CredentialRead(
            id=credential.id,
            name=credential.name,
            description=credential.description,
            credential_type=credential.credential_type,
            username=credential.username,
            masked_secret="********" if credential.encrypted_secret or credential.private_key else "",
            tags=credential.tags,
            scope=credential.scope,
            created_at=credential.created_at,
            updated_at=credential.updated_at,
        )
