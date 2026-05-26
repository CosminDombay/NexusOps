"""runtime refresh stabilization

Revision ID: 20260526_0034
Revises: 20260526_0033
Create Date: 2026-05-26 13:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260526_0034"
down_revision: str | None = "20260526_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("deployment_targets", sa.Column("runtime_state", sa.String(length=50), nullable=False, server_default="unknown"))
    op.add_column("deployment_targets", sa.Column("health_state", sa.String(length=50), nullable=False, server_default="unknown"))
    op.add_column("deployment_targets", sa.Column("sync_status", sa.String(length=50), nullable=False, server_default="unknown"))
    op.add_column("deployment_targets", sa.Column("runtime_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("deployment_targets", sa.Column("runtime_error", sa.Text(), nullable=True))
    op.add_column("deployment_targets", sa.Column("runtime_containers", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("deployment_targets", sa.Column("missing_services", sa.JSON(), nullable=False, server_default="[]"))
    op.create_index(op.f("ix_deployment_targets_runtime_state"), "deployment_targets", ["runtime_state"], unique=False)
    op.create_index(op.f("ix_deployment_targets_health_state"), "deployment_targets", ["health_state"], unique=False)
    op.create_index(op.f("ix_deployment_targets_sync_status"), "deployment_targets", ["sync_status"], unique=False)
    op.create_index(op.f("ix_deployment_targets_runtime_checked_at"), "deployment_targets", ["runtime_checked_at"], unique=False)
    op.alter_column("deployment_targets", "runtime_state", server_default=None)
    op.alter_column("deployment_targets", "health_state", server_default=None)
    op.alter_column("deployment_targets", "sync_status", server_default=None)
    op.alter_column("deployment_targets", "runtime_containers", server_default=None)
    op.alter_column("deployment_targets", "missing_services", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_deployment_targets_runtime_checked_at"), table_name="deployment_targets")
    op.drop_index(op.f("ix_deployment_targets_sync_status"), table_name="deployment_targets")
    op.drop_index(op.f("ix_deployment_targets_health_state"), table_name="deployment_targets")
    op.drop_index(op.f("ix_deployment_targets_runtime_state"), table_name="deployment_targets")
    op.drop_column("deployment_targets", "missing_services")
    op.drop_column("deployment_targets", "runtime_containers")
    op.drop_column("deployment_targets", "runtime_error")
    op.drop_column("deployment_targets", "runtime_checked_at")
    op.drop_column("deployment_targets", "sync_status")
    op.drop_column("deployment_targets", "health_state")
    op.drop_column("deployment_targets", "runtime_state")
