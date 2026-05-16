from cryptography.fernet import Fernet, InvalidToken

from backend.app.core.config import settings


class EncryptionConfigurationError(Exception):
    """Raised when secret encryption is not configured."""


class SecretDecryptionError(Exception):
    """Raised when an encrypted secret cannot be decrypted."""


class EncryptionService:
    """Fernet-backed encryption for stored credential values."""

    def __init__(self, master_key: str | None = None) -> None:
        self.master_key = master_key or settings.nexusops_master_key

    def _fernet(self) -> Fernet:
        if not self.master_key:
            raise EncryptionConfigurationError("NEXUSOPS_MASTER_KEY is required for credential encryption")
        try:
            return Fernet(self.master_key.encode("utf-8"))
        except ValueError as exc:
            raise EncryptionConfigurationError("NEXUSOPS_MASTER_KEY must be a valid Fernet key") from exc

    def encrypt_value(self, value: str | None) -> str | None:
        if value is None:
            return None
        return self._fernet().encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt_value(self, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return self._fernet().decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise SecretDecryptionError("Credential secret could not be decrypted") from exc
