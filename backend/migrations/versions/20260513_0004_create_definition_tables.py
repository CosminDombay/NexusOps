"""create package and profile definition tables

Revision ID: 20260513_0004
Revises: 20260513_0003
Create Date: 2026-05-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260513_0004"
down_revision: Union[str, None] = "20260513_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "package_definitions",
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("supported_os", sa.JSON(), nullable=False),
        sa.Column("install_command", sa.Text(), nullable=False),
        sa.Column("validation_command", sa.Text(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_builtin", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_package_definitions")),
        sa.UniqueConstraint("slug", name="uq_package_definitions_slug"),
    )
    op.create_index(op.f("ix_package_definitions_category"), "package_definitions", ["category"])
    op.create_index(op.f("ix_package_definitions_created_at"), "package_definitions", ["created_at"])
    op.create_index(op.f("ix_package_definitions_slug"), "package_definitions", ["slug"])

    op.create_table(
        "infrastructure_profiles",
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("is_builtin", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_infrastructure_profiles")),
        sa.UniqueConstraint("slug", name="uq_infrastructure_profiles_slug"),
    )
    op.create_index(op.f("ix_infrastructure_profiles_category"), "infrastructure_profiles", ["category"])
    op.create_index(op.f("ix_infrastructure_profiles_created_at"), "infrastructure_profiles", ["created_at"])
    op.create_index(op.f("ix_infrastructure_profiles_slug"), "infrastructure_profiles", ["slug"])


def downgrade() -> None:
    op.drop_index(op.f("ix_infrastructure_profiles_slug"), table_name="infrastructure_profiles")
    op.drop_index(op.f("ix_infrastructure_profiles_created_at"), table_name="infrastructure_profiles")
    op.drop_index(op.f("ix_infrastructure_profiles_category"), table_name="infrastructure_profiles")
    op.drop_table("infrastructure_profiles")

    op.drop_index(op.f("ix_package_definitions_slug"), table_name="package_definitions")
    op.drop_index(op.f("ix_package_definitions_created_at"), table_name="package_definitions")
    op.drop_index(op.f("ix_package_definitions_category"), table_name="package_definitions")
    op.drop_table("package_definitions")
