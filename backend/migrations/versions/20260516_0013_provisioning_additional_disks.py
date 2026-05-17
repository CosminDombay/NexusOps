"""provisioning additional disks

Revision ID: 20260516_0013
Revises: 20260516_0012
Create Date: 2026-05-16 20:55:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260516_0013"
down_revision: str | None = "20260516_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "provisioning_requests",
        sa.Column("additional_disks", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.alter_column("provisioning_requests", "additional_disks", server_default=None)


def downgrade() -> None:
    op.drop_column("provisioning_requests", "additional_disks")
