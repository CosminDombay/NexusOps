"""deployment and integration credential refs

Revision ID: 20260516_0012
Revises: 20260516_0011
Create Date: 2026-05-16 20:35:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260516_0012"
down_revision: str | None = "20260516_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("deployments", sa.Column("credential_refs", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("integrations", sa.Column("credential_refs", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.alter_column("deployments", "credential_refs", server_default=None)
    op.alter_column("integrations", "credential_refs", server_default=None)


def downgrade() -> None:
    op.drop_column("integrations", "credential_refs")
    op.drop_column("deployments", "credential_refs")
