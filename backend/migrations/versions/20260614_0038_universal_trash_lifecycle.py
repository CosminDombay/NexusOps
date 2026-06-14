"""universal trash lifecycle

Revision ID: 20260614_0038
Revises: 20260614_0037
Create Date: 2026-06-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260614_0038"
down_revision: str | None = "20260614_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TRASH_TABLES = (
    "package_definitions",
    "infrastructure_profiles",
    "automations",
    "custom_operational_actions",
    "deployments",
    "integrations",
    "provisioning_requests",
    "provisioning_blueprints",
)


def upgrade() -> None:
    for table in TRASH_TABLES:
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("deleted_by", sa.String(length=255), nullable=True))
        op.add_column(table, sa.Column("delete_reason", sa.Text(), nullable=True))
        op.create_index(op.f(f"ix_{table}_deleted_at"), table, ["deleted_at"], unique=False)


def downgrade() -> None:
    for table in reversed(TRASH_TABLES):
        op.drop_index(op.f(f"ix_{table}_deleted_at"), table_name=table)
        op.drop_column(table, "delete_reason")
        op.drop_column(table, "deleted_by")
        op.drop_column(table, "deleted_at")
