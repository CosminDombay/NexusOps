"""identity profile steps

Revision ID: 20260614_0036
Revises: 20260604_0035
Create Date: 2026-06-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260614_0036"
down_revision: str | None = "20260604_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("linux_users", sa.Column("password_credential_ref", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("linux_users", "password_credential_ref")
