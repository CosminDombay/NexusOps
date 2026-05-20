"""add lxc provisioning metadata

Revision ID: 20260520_0024
Revises: 20260519_0023
Create Date: 2026-05-20 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260520_0024"
down_revision: str | None = "20260519_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "provisioning_requests",
        sa.Column("provisioning_type", sa.String(length=20), nullable=False, server_default="qemu"),
    )
    op.add_column(
        "provisioning_requests",
        sa.Column("template_ref", sa.String(length=500), nullable=True),
    )
    op.create_index(
        op.f("ix_provisioning_requests_provisioning_type"),
        "provisioning_requests",
        ["provisioning_type"],
        unique=False,
    )
    op.alter_column("provisioning_requests", "provisioning_type", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_provisioning_requests_provisioning_type"), table_name="provisioning_requests")
    op.drop_column("provisioning_requests", "template_ref")
    op.drop_column("provisioning_requests", "provisioning_type")
