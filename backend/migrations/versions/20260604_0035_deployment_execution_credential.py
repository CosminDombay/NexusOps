"""execution credential references

Revision ID: 20260604_0035
Revises: 20260526_0034
Create Date: 2026-06-04 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260604_0035"
down_revision: str | None = "20260526_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("deployments", sa.Column("execution_credential_ref", sa.String(length=255), nullable=True))
    op.add_column("automations", sa.Column("execution_credential_ref", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("automations", "execution_credential_ref")
    op.drop_column("deployments", "execution_credential_ref")
