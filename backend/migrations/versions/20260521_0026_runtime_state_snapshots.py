"""runtime state snapshots

Revision ID: 20260521_0026
Revises: 20260520_0025
Create Date: 2026-05-21 13:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260521_0026"
down_revision: str | None = "20260520_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "node_runtime_snapshots",
        sa.Column("node_id", sa.Uuid(), nullable=False),
        sa.Column("provider_state", sa.String(length=100), nullable=False),
        sa.Column("provider_reachable", sa.Boolean(), nullable=False),
        sa.Column("provider_guest_exists", sa.Boolean(), nullable=False),
        sa.Column("ssh_state", sa.String(length=100), nullable=False),
        sa.Column("monitoring_state", sa.String(length=100), nullable=False),
        sa.Column("readiness_state", sa.String(length=100), nullable=False),
        sa.Column("orchestration_state", sa.String(length=100), nullable=False),
        sa.Column("lifecycle_state", sa.String(length=100), nullable=False),
        sa.Column("eligibility", sa.JSON(), nullable=False),
        sa.Column("degraded_reasons", sa.JSON(), nullable=False),
        sa.Column("stale_reasons", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("monitoring_targets", sa.JSON(), nullable=False),
        sa.Column("observability", sa.JSON(), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stale_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refresh_scope", sa.String(length=100), nullable=False),
        sa.Column("refresh_status", sa.String(length=50), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["node_id"], ["servers.id"], name=op.f("fk_node_runtime_snapshots_node_id_servers"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_node_runtime_snapshots")),
        sa.UniqueConstraint("node_id", name="uq_node_runtime_snapshots_node_id"),
    )
    for column in (
        "node_id",
        "provider_state",
        "ssh_state",
        "monitoring_state",
        "readiness_state",
        "orchestration_state",
        "lifecycle_state",
        "last_checked_at",
        "stale_after",
        "refresh_scope",
        "refresh_status",
    ):
        op.create_index(op.f(f"ix_node_runtime_snapshots_{column}"), "node_runtime_snapshots", [column])

    op.create_table(
        "runtime_refresh_events",
        sa.Column("scope", sa.String(length=100), nullable=False),
        sa.Column("node_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["node_id"], ["servers.id"], name=op.f("fk_runtime_refresh_events_node_id_servers"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_runtime_refresh_events")),
    )
    op.create_index(op.f("ix_runtime_refresh_events_scope"), "runtime_refresh_events", ["scope"])
    op.create_index(op.f("ix_runtime_refresh_events_node_id"), "runtime_refresh_events", ["node_id"])
    op.create_index(op.f("ix_runtime_refresh_events_status"), "runtime_refresh_events", ["status"])

    op.create_table(
        "runtime_refresh_status",
        sa.Column("scope", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_runtime_refresh_status")),
        sa.UniqueConstraint("scope", name="uq_runtime_refresh_status_scope"),
    )
    op.create_index(op.f("ix_runtime_refresh_status_scope"), "runtime_refresh_status", ["scope"])
    op.create_index(op.f("ix_runtime_refresh_status_status"), "runtime_refresh_status", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_runtime_refresh_status_status"), table_name="runtime_refresh_status")
    op.drop_index(op.f("ix_runtime_refresh_status_scope"), table_name="runtime_refresh_status")
    op.drop_table("runtime_refresh_status")
    op.drop_index(op.f("ix_runtime_refresh_events_status"), table_name="runtime_refresh_events")
    op.drop_index(op.f("ix_runtime_refresh_events_node_id"), table_name="runtime_refresh_events")
    op.drop_index(op.f("ix_runtime_refresh_events_scope"), table_name="runtime_refresh_events")
    op.drop_table("runtime_refresh_events")
    for column in (
        "refresh_status",
        "refresh_scope",
        "stale_after",
        "last_checked_at",
        "lifecycle_state",
        "orchestration_state",
        "readiness_state",
        "monitoring_state",
        "ssh_state",
        "provider_state",
        "node_id",
    ):
        op.drop_index(op.f(f"ix_node_runtime_snapshots_{column}"), table_name="node_runtime_snapshots")
    op.drop_table("node_runtime_snapshots")
