"""audit events and monitoring validation attempts

Revision ID: 20260523_0030
Revises: 20260523_0029
Create Date: 2026-05-23 23:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260523_0030"
down_revision: str | None = "20260523_0029"
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


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_username", sa.String(length=255), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_type", sa.String(length=120), nullable=True),
        sa.Column("target_id", sa.String(length=120), nullable=True),
        sa.Column("result", sa.String(length=50), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("source_ip", sa.String(length=64), nullable=True),
        sa.Column("correlation_id", sa.String(length=120), nullable=True),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], name=op.f("fk_audit_events_actor_user_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_runs.id"], name=op.f("fk_audit_events_workflow_run_id_workflow_runs"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    for column in (
        "event_type",
        "actor_user_id",
        "actor_username",
        "occurred_at",
        "target_type",
        "target_id",
        "result",
        "correlation_id",
        "workflow_run_id",
    ):
        op.create_index(op.f(f"ix_audit_events_{column}"), "audit_events", [column])

    op.create_table(
        "monitoring_validation_attempts",
        sa.Column("server_id", sa.Uuid(), nullable=False),
        sa.Column("monitoring_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("audit_event_id", sa.Uuid(), nullable=True),
        sa.Column("validation_method", sa.String(length=100), nullable=False),
        sa.Column("component_results", sa.JSON(), nullable=False),
        sa.Column("monitoring_state", monitoring_state, nullable=False),
        sa.Column("result", sa.String(length=50), nullable=False),
        sa.Column("failure_reason", sa.String(length=100), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["audit_event_id"], ["audit_events.id"], name=op.f("fk_monitoring_validation_attempts_audit_event_id_audit_events"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["monitoring_snapshot_id"], ["monitoring_snapshots.id"], name=op.f("fk_monitoring_validation_attempts_monitoring_snapshot_id_monitoring_snapshots"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], name=op.f("fk_monitoring_validation_attempts_server_id_servers"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_monitoring_validation_attempts")),
    )
    for column in (
        "server_id",
        "monitoring_snapshot_id",
        "audit_event_id",
        "monitoring_state",
        "result",
        "failure_reason",
        "started_at",
        "finished_at",
    ):
        op.create_index(op.f(f"ix_monitoring_validation_attempts_{column}"), "monitoring_validation_attempts", [column])


def downgrade() -> None:
    for column in (
        "finished_at",
        "started_at",
        "failure_reason",
        "result",
        "monitoring_state",
        "audit_event_id",
        "monitoring_snapshot_id",
        "server_id",
    ):
        op.drop_index(op.f(f"ix_monitoring_validation_attempts_{column}"), table_name="monitoring_validation_attempts")
    op.drop_table("monitoring_validation_attempts")

    for column in (
        "workflow_run_id",
        "correlation_id",
        "result",
        "target_id",
        "target_type",
        "occurred_at",
        "actor_username",
        "actor_user_id",
        "event_type",
    ):
        op.drop_index(op.f(f"ix_audit_events_{column}"), table_name="audit_events")
    op.drop_table("audit_events")
