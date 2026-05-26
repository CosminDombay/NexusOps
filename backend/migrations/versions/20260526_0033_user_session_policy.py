"""user session policy

Revision ID: 20260526_0033
Revises: 20260526_0032
Create Date: 2026-05-26 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260526_0033"
down_revision: str | None = "20260526_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("session_inactivity_timeout_minutes", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "session_inactivity_timeout_minutes")
