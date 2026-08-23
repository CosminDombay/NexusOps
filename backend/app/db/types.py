"""Reusable SQLAlchemy column types.

``EncryptedString`` keeps secrets that are stored directly on a domain record
(rather than in the Credential Manager) encrypted at rest with the same Fernet
master key used by :mod:`backend.app.modules.credentials.encryption_service`.
"""

from __future__ import annotations

import structlog
from sqlalchemy import Text, TypeDecorator

from backend.app.modules.credentials.encryption_service import (
    EncryptionConfigurationError,
    EncryptionService,
    SecretDecryptionError,
)

logger = structlog.get_logger(__name__)

# Fernet tokens are URL-safe base64 and always carry this version byte.
_FERNET_PREFIX = "gAAAAA"


class EncryptedString(TypeDecorator):
    """Transparently encrypt a string column at rest.

    Reads tolerate values written before this column was encrypted: anything
    that is not a Fernet token is returned unchanged, and is re-encrypted the
    next time the record is written. That keeps existing rows readable without
    requiring the master key to be present during schema migration.
    """

    impl = Text
    cache_ok = True

    @property
    def _service(self) -> EncryptionService:
        # Constructed per access so a master key supplied after import is picked up.
        return EncryptionService()

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        if value is None or value == "":
            return value
        try:
            return self._service.encrypt_value(value)
        except EncryptionConfigurationError:
            # Without a master key the platform cannot encrypt. Storing plaintext
            # preserves pre-existing behaviour for unconfigured local setups; the
            # startup warning tells the operator to configure NEXUSOPS_MASTER_KEY.
            logger.warning("db.secret_stored_unencrypted", reason="master_key_missing")
            return value

    def process_result_value(self, value: str | None, dialect) -> str | None:
        if value is None or value == "":
            return value
        if not value.startswith(_FERNET_PREFIX):
            return value  # legacy plaintext row
        try:
            return self._service.decrypt_value(value)
        except (EncryptionConfigurationError, SecretDecryptionError):
            logger.error("db.secret_decrypt_failed")
            raise
