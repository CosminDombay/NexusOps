"""credential trash lifecycle

Revision ID: 20260614_0037
Revises: 20260614_0036
Create Date: 2026-06-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260614_0037"
down_revision: str | None = "20260614_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("credentials", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("credentials", sa.Column("deleted_by", sa.String(length=255), nullable=True))
    op.add_column("credentials", sa.Column("delete_reason", sa.Text(), nullable=True))
    op.create_index(op.f("ix_credentials_deleted_at"), "credentials", ["deleted_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_credentials_deleted_at"), table_name="credentials")
    op.drop_column("credentials", "delete_reason")
    op.drop_column("credentials", "deleted_by")
    op.drop_column("credentials", "deleted_at")
