"""create custom operational actions

Revision ID: 20260518_0020
Revises: 20260518_0019
Create Date: 2026-05-18 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260518_0020"
down_revision: str | None = "20260518_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "custom_operational_actions",
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("destructive", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_custom_operational_actions")),
        sa.UniqueConstraint("slug", name=op.f("uq_custom_operational_actions_slug")),
    )
    op.create_index(op.f("ix_custom_operational_actions_category"), "custom_operational_actions", ["category"])
    op.create_index(op.f("ix_custom_operational_actions_name"), "custom_operational_actions", ["name"])
    op.create_index(op.f("ix_custom_operational_actions_slug"), "custom_operational_actions", ["slug"])


def downgrade() -> None:
    op.drop_index(op.f("ix_custom_operational_actions_slug"), table_name="custom_operational_actions")
    op.drop_index(op.f("ix_custom_operational_actions_name"), table_name="custom_operational_actions")
    op.drop_index(op.f("ix_custom_operational_actions_category"), table_name="custom_operational_actions")
    op.drop_table("custom_operational_actions")
