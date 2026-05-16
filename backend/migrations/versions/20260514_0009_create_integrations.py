"""create integrations

Revision ID: 20260514_0009
Revises: 20260514_0008
Create Date: 2026-05-14 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260514_0009"
down_revision: str | None = "20260514_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    integration_type = postgresql.ENUM(
        "infrastructure_provider",
        "monitoring",
        "networking",
        "database",
        name="integration_type",
    )
    integration_type.create(op.get_bind(), checkfirst=True)
    integration_type_column = postgresql.ENUM(
        "infrastructure_provider",
        "monitoring",
        "networking",
        "database",
        name="integration_type",
        create_type=False,
    )
    op.create_table(
        "integrations",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", integration_type_column, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integrations")),
    )
    op.create_index(op.f("ix_integrations_enabled"), "integrations", ["enabled"], unique=False)
    op.create_index(op.f("ix_integrations_name"), "integrations", ["name"], unique=False)
    op.create_index(op.f("ix_integrations_type"), "integrations", ["type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_integrations_type"), table_name="integrations")
    op.drop_index(op.f("ix_integrations_name"), table_name="integrations")
    op.drop_index(op.f("ix_integrations_enabled"), table_name="integrations")
    op.drop_table("integrations")
    sa.Enum(name="integration_type").drop(op.get_bind(), checkfirst=True)
