"""create provisioning blueprints

Revision ID: 20260517_0014
Revises: 20260516_0013
Create Date: 2026-05-17 00:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260517_0014"
down_revision: str | None = "20260516_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provisioning_blueprints",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_node", sa.String(length=100), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("cpu_cores", sa.Integer(), nullable=False),
        sa.Column("memory_mb", sa.Integer(), nullable=False),
        sa.Column("disk_gb", sa.Integer(), nullable=False),
        sa.Column("additional_disks", sa.JSON(), nullable=False),
        sa.Column("network_bridge", sa.String(length=100), nullable=False),
        sa.Column("environment", sa.String(length=100), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("start_on_boot", sa.Boolean(), nullable=False),
        sa.Column("cloud_init_username", sa.String(length=100), nullable=False),
        sa.Column("ssh_public_key", sa.Text(), nullable=True),
        sa.Column("gateway", sa.String(length=64), nullable=False),
        sa.Column("dns_servers", sa.JSON(), nullable=False),
        sa.Column("bootstrap_profile_ids", sa.JSON(), nullable=False),
        sa.Column("bootstrap_package_ids", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provisioning_blueprints")),
        sa.UniqueConstraint("name", name="uq_provisioning_blueprints_name"),
    )
    op.create_index(op.f("ix_provisioning_blueprints_environment"), "provisioning_blueprints", ["environment"], unique=False)
    op.create_index(op.f("ix_provisioning_blueprints_name"), "provisioning_blueprints", ["name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_provisioning_blueprints_name"), table_name="provisioning_blueprints")
    op.drop_index(op.f("ix_provisioning_blueprints_environment"), table_name="provisioning_blueprints")
    op.drop_table("provisioning_blueprints")
