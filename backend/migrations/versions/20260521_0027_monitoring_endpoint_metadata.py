"""monitoring endpoint metadata

Revision ID: 20260521_0027
Revises: 20260521_0026
Create Date: 2026-05-21 14:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260521_0027"
down_revision: str | None = "20260521_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("servers", sa.Column("monitoring_interface", sa.String(length=50), nullable=True))
    op.add_column("servers", sa.Column("monitoring_target", sa.String(length=255), nullable=True))
    op.add_column("servers", sa.Column("monitoring_strategy", sa.String(length=100), nullable=True))
    op.create_index(op.f("ix_servers_monitoring_interface"), "servers", ["monitoring_interface"])
    op.create_index(op.f("ix_servers_monitoring_target"), "servers", ["monitoring_target"])
    op.create_index(op.f("ix_servers_monitoring_strategy"), "servers", ["monitoring_strategy"])


def downgrade() -> None:
    op.drop_index(op.f("ix_servers_monitoring_strategy"), table_name="servers")
    op.drop_index(op.f("ix_servers_monitoring_target"), table_name="servers")
    op.drop_index(op.f("ix_servers_monitoring_interface"), table_name="servers")
    op.drop_column("servers", "monitoring_strategy")
    op.drop_column("servers", "monitoring_target")
    op.drop_column("servers", "monitoring_interface")
