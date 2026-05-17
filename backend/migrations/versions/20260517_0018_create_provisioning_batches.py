"""create provisioning batches

Revision ID: 20260517_0018
Revises: 20260517_0017
Create Date: 2026-05-17 18:15:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260517_0018"
down_revision: str | None = "20260517_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    batch_status = sa.Enum(
        "requested",
        "running",
        "completed",
        "partial_failed",
        "failed",
        name="provisioning_batch_status",
    )
    op.create_table(
        "provisioning_batches",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("blueprint_id", sa.Uuid(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("vm_name_pattern", sa.String(length=255), nullable=False),
        sa.Column("hostname_pattern", sa.String(length=255), nullable=False),
        sa.Column("starting_vm_id", sa.Integer(), nullable=False),
        sa.Column("starting_ip_cidr", sa.String(length=64), nullable=False),
        sa.Column("status", batch_status, nullable=False),
        sa.Column("completed_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["blueprint_id"],
            ["provisioning_blueprints.id"],
            name=op.f("fk_provisioning_batches_blueprint_id_provisioning_blueprints"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provisioning_batches")),
    )
    op.create_index(op.f("ix_provisioning_batches_blueprint_id"), "provisioning_batches", ["blueprint_id"], unique=False)
    op.create_index(op.f("ix_provisioning_batches_name"), "provisioning_batches", ["name"], unique=False)
    op.create_index(op.f("ix_provisioning_batches_status"), "provisioning_batches", ["status"], unique=False)
    op.add_column("provisioning_requests", sa.Column("batch_id", sa.Uuid(), nullable=True))
    op.add_column("provisioning_requests", sa.Column("batch_index", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_provisioning_requests_batch_id"), "provisioning_requests", ["batch_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_provisioning_requests_batch_id_provisioning_batches"),
        "provisioning_requests",
        "provisioning_batches",
        ["batch_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_provisioning_requests_batch_id_provisioning_batches"), "provisioning_requests", type_="foreignkey")
    op.drop_index(op.f("ix_provisioning_requests_batch_id"), table_name="provisioning_requests")
    op.drop_column("provisioning_requests", "batch_index")
    op.drop_column("provisioning_requests", "batch_id")
    op.drop_index(op.f("ix_provisioning_batches_status"), table_name="provisioning_batches")
    op.drop_index(op.f("ix_provisioning_batches_name"), table_name="provisioning_batches")
    op.drop_index(op.f("ix_provisioning_batches_blueprint_id"), table_name="provisioning_batches")
    op.drop_table("provisioning_batches")
    sa.Enum(name="provisioning_batch_status").drop(op.get_bind(), checkfirst=True)
