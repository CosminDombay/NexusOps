"""ssh key planned assignment

Revision ID: 20260618_0040
Revises: 20260618_0039
Create Date: 2026-06-18 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260618_0040"
down_revision: str | None = "20260618_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ssh_keys", sa.Column("assigned_username", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("ssh_keys", "assigned_username")
