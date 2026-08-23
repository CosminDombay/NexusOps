"""encrypt inline server ssh passwords at rest

Widens servers.ssh_password to TEXT (Fernet tokens are longer than the plaintext
they replace) and encrypts any existing plaintext values in place.

Encryption requires NEXUSOPS_MASTER_KEY. When it is absent the schema change
still applies and existing rows are left as-is: the application reads legacy
plaintext transparently and re-encrypts each row on its next write.

Revision ID: 20260819_0044
Revises: 20260625_0043
Create Date: 2026-08-19 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_0044"
down_revision: str | None = "20260625_0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FERNET_PREFIX = "gAAAAA"


def upgrade() -> None:
    op.alter_column(
        "servers",
        "ssh_password",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=True,
    )
    _rewrite_secrets(encrypt=True)


def downgrade() -> None:
    _rewrite_secrets(encrypt=False)
    op.alter_column(
        "servers",
        "ssh_password",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=True,
    )


def _rewrite_secrets(*, encrypt: bool) -> None:
    """Encrypt or decrypt existing inline SSH passwords in place."""
    from backend.app.modules.credentials.encryption_service import (
        EncryptionConfigurationError,
        EncryptionService,
        SecretDecryptionError,
    )

    service = EncryptionService()
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, ssh_password FROM servers WHERE ssh_password IS NOT NULL AND ssh_password <> ''")
    ).fetchall()
    if not rows:
        return

    for row_id, value in rows:
        already_encrypted = value.startswith(_FERNET_PREFIX)
        if encrypt == already_encrypted:
            continue
        try:
            rewritten = service.encrypt_value(value) if encrypt else service.decrypt_value(value)
        except EncryptionConfigurationError:
            # No master key configured: leave rows untouched. The application
            # handles mixed plaintext/ciphertext rows transparently.
            return
        except SecretDecryptionError:
            # Written under a different master key; leave it rather than destroy it.
            continue
        connection.execute(
            sa.text("UPDATE servers SET ssh_password = :value WHERE id = :id"),
            {"value": rewritten, "id": row_id},
        )
