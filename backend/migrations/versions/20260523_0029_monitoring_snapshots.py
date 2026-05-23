"""monitoring snapshots

Revision ID: 20260523_0029
Revises: 20260523_0028
Create Date: 2026-05-23 19:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260523_0029"
down_revision: str | None = "20260523_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


monitoring_state = postgresql.ENUM(
    "monitored",
    "partial",
    "unmonitored",
    "stale",
    "unknown",
    name="monitoring_state",
    create_type=False,
)
monitoring_component_status = postgresql.ENUM(
    "healthy",
    "unavailable",
    "not_configured",
    "unknown",
    name="monitoring_component_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM(
        "monitored",
        "partial",
        "unmonitored",
        "stale",
        "unknown",
        name="monitoring_state",
    ).create(bind, checkfirst=True)
    postgresql.ENUM(
        "healthy",
        "unavailable",
        "not_configured",
        "unknown",
        name="monitoring_component_status",
    ).create(bind, checkfirst=True)
    op.create_table(
        "monitoring_snapshots",
        sa.Column("server_id", sa.Uuid(), nullable=False),
        sa.Column("integration_id", sa.Uuid(), nullable=True),
        sa.Column("monitoring_state", monitoring_state, nullable=False),
        sa.Column("node_exporter_status", monitoring_component_status, nullable=False),
        sa.Column("promtail_status", monitoring_component_status, nullable=False),
        sa.Column("cadvisor_status", monitoring_component_status, nullable=False),
        sa.Column("prometheus_target_health", monitoring_component_status, nullable=False),
        sa.Column("monitoring_target", sa.String(length=255), nullable=True),
        sa.Column("grafana_url", sa.String(length=1000), nullable=True),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stale_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"], name=op.f("fk_monitoring_snapshots_integration_id_integrations"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], name=op.f("fk_monitoring_snapshots_server_id_servers"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_monitoring_snapshots")),
        sa.UniqueConstraint("server_id", name="uq_monitoring_snapshots_server_id"),
    )
    for column in (
        "server_id",
        "integration_id",
        "monitoring_state",
        "last_validated_at",
        "last_successful_check_at",
        "stale_after",
    ):
        op.create_index(op.f(f"ix_monitoring_snapshots_{column}"), "monitoring_snapshots", [column])


def downgrade() -> None:
    for column in (
        "stale_after",
        "last_successful_check_at",
        "last_validated_at",
        "monitoring_state",
        "integration_id",
        "server_id",
    ):
        op.drop_index(op.f(f"ix_monitoring_snapshots_{column}"), table_name="monitoring_snapshots")
    op.drop_table("monitoring_snapshots")
    bind = op.get_bind()
    monitoring_component_status.drop(bind, checkfirst=True)
    monitoring_state.drop(bind, checkfirst=True)
