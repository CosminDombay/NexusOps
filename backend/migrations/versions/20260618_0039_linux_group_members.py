"""linux group planned members

Revision ID: 20260618_0039
Revises: 20260614_0038
Create Date: 2026-06-18 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260618_0039"
down_revision: str | None = "20260614_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("linux_groups", sa.Column("members", sa.JSON(), nullable=True))
    op.execute("UPDATE linux_groups SET members = '[]' WHERE members IS NULL")
    op.alter_column("linux_groups", "members", nullable=False)


def downgrade() -> None:
    op.drop_column("linux_groups", "members")
