"""provisioning bootstrap templates

Revision ID: 20260620_0042
Revises: 20260620_0041
Create Date: 2026-06-20 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260620_0042"
down_revision: str | None = "20260620_0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provisioning_bootstrap_templates",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("bootstrap_items", sa.JSON(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(length=255), nullable=True),
        sa.Column("delete_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_provisioning_bootstrap_templates_name"),
    )
    op.create_index(
        op.f("ix_provisioning_bootstrap_templates_deleted_at"),
        "provisioning_bootstrap_templates",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provisioning_bootstrap_templates_name"),
        "provisioning_bootstrap_templates",
        ["name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_provisioning_bootstrap_templates_name"), table_name="provisioning_bootstrap_templates")
    op.drop_index(op.f("ix_provisioning_bootstrap_templates_deleted_at"), table_name="provisioning_bootstrap_templates")
    op.drop_table("provisioning_bootstrap_templates")
