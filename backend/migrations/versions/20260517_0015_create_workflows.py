"""create workflows

Revision ID: 20260517_0015
Revises: 20260517_0014
Create Date: 2026-05-17 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260517_0015"
down_revision: str | None = "20260517_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    workflow_type = sa.Enum(
        "provision_vm",
        "profile_execution",
        "package_execution",
        "deployment_execution",
        "scheduled_action",
        "scheduled_profile",
        "scheduled_package",
        name="workflow_type",
    )
    workflow_status = sa.Enum("pending", "queued", "running", "success", "failed", "cancelled", name="workflow_status")
    workflow_trigger_source = sa.Enum("manual", "scheduled", "provisioning", "system", name="workflow_trigger_source")
    workflow_step_status = sa.Enum("pending", "running", "success", "failed", "skipped", name="workflow_step_status")

    op.create_table(
        "workflow_runs",
        sa.Column("workflow_type", workflow_type, nullable=False),
        sa.Column("status", workflow_status, nullable=False),
        sa.Column("trigger_source", workflow_trigger_source, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("target_server_id", sa.Uuid(), nullable=True),
        sa.Column("initiated_by", sa.String(length=255), nullable=True),
        sa.Column("context_json", sa.JSON(), nullable=False),
        sa.Column("result_summary", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["target_server_id"], ["servers.id"], name=op.f("fk_workflow_runs_target_server_id_servers")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_runs")),
    )
    op.create_index(op.f("ix_workflow_runs_status"), "workflow_runs", ["status"], unique=False)
    op.create_index(op.f("ix_workflow_runs_target_server_id"), "workflow_runs", ["target_server_id"], unique=False)
    op.create_index(op.f("ix_workflow_runs_trigger_source"), "workflow_runs", ["trigger_source"], unique=False)
    op.create_index(op.f("ix_workflow_runs_workflow_type"), "workflow_runs", ["workflow_type"], unique=False)

    op.create_table(
        "workflow_steps",
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", workflow_step_status, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("log_output", sa.Text(), nullable=False),
        sa.Column("error_output", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_runs.id"], name=op.f("fk_workflow_steps_workflow_run_id_workflow_runs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_steps")),
    )
    op.create_index(op.f("ix_workflow_steps_status"), "workflow_steps", ["status"], unique=False)
    op.create_index(op.f("ix_workflow_steps_step_type"), "workflow_steps", ["step_type"], unique=False)
    op.create_index(op.f("ix_workflow_steps_workflow_run_id"), "workflow_steps", ["workflow_run_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_workflow_steps_workflow_run_id"), table_name="workflow_steps")
    op.drop_index(op.f("ix_workflow_steps_step_type"), table_name="workflow_steps")
    op.drop_index(op.f("ix_workflow_steps_status"), table_name="workflow_steps")
    op.drop_table("workflow_steps")
    op.drop_index(op.f("ix_workflow_runs_workflow_type"), table_name="workflow_runs")
    op.drop_index(op.f("ix_workflow_runs_trigger_source"), table_name="workflow_runs")
    op.drop_index(op.f("ix_workflow_runs_target_server_id"), table_name="workflow_runs")
    op.drop_index(op.f("ix_workflow_runs_status"), table_name="workflow_runs")
    op.drop_table("workflow_runs")
    sa.Enum(name="workflow_step_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="workflow_trigger_source").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="workflow_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="workflow_type").drop(op.get_bind(), checkfirst=True)
