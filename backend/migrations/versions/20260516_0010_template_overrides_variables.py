"""template overrides and variables

Revision ID: 20260516_0010
Revises: 20260514_0009
Create Date: 2026-05-16 14:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260516_0010"
down_revision: str | None = "20260514_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("package_definitions", sa.Column("uninstall_command", sa.Text(), nullable=False, server_default=""))
    op.add_column("package_definitions", sa.Column("variables", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("package_definitions", sa.Column("is_modified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("package_definitions", sa.Column("base_version", sa.String(length=50), nullable=True))
    op.add_column("package_definitions", sa.Column("source_template_id", sa.String(length=100), nullable=True))
    op.add_column("package_definitions", sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_package_definitions_source_template_id"), "package_definitions", ["source_template_id"], unique=False)

    op.add_column("infrastructure_profiles", sa.Column("variables", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("infrastructure_profiles", sa.Column("is_modified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("infrastructure_profiles", sa.Column("base_version", sa.String(length=50), nullable=True))
    op.add_column("infrastructure_profiles", sa.Column("source_template_id", sa.String(length=100), nullable=True))
    op.add_column("infrastructure_profiles", sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_infrastructure_profiles_source_template_id"), "infrastructure_profiles", ["source_template_id"], unique=False)

    op.alter_column("package_definitions", "uninstall_command", server_default=None)
    op.alter_column("package_definitions", "variables", server_default=None)
    op.alter_column("package_definitions", "is_modified", server_default=None)
    op.alter_column("infrastructure_profiles", "variables", server_default=None)
    op.alter_column("infrastructure_profiles", "is_modified", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_infrastructure_profiles_source_template_id"), table_name="infrastructure_profiles")
    op.drop_column("infrastructure_profiles", "modified_at")
    op.drop_column("infrastructure_profiles", "source_template_id")
    op.drop_column("infrastructure_profiles", "base_version")
    op.drop_column("infrastructure_profiles", "is_modified")
    op.drop_column("infrastructure_profiles", "variables")

    op.drop_index(op.f("ix_package_definitions_source_template_id"), table_name="package_definitions")
    op.drop_column("package_definitions", "modified_at")
    op.drop_column("package_definitions", "source_template_id")
    op.drop_column("package_definitions", "base_version")
    op.drop_column("package_definitions", "is_modified")
    op.drop_column("package_definitions", "variables")
    op.drop_column("package_definitions", "uninstall_command")
