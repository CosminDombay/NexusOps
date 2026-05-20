"""deployment runtime executions

Revision ID: 20260520_0025
Revises: 20260520_0024
Create Date: 2026-05-20 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260520_0025"
down_revision: str | None = "20260520_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for value in ("queued", "success", "partial_success", "degraded", "cancelled"):
            op.execute(f"ALTER TYPE deployment_status ADD VALUE IF NOT EXISTS '{value}'")

    deployment_status = postgresql.ENUM(
        "draft",
        "queued",
        "deploying",
        "running",
        "success",
        "partial_success",
        "degraded",
        "stopped",
        "failed",
        "cancelled",
        name="deployment_status",
        create_type=False,
    )

    op.create_table(
        "deployment_executions",
        sa.Column("deployment_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(length=50), nullable=False),
        sa.Column("status", deployment_status, nullable=False),
        sa.Column("trigger_source", sa.String(length=100), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_summary", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployments.id"], name=op.f("fk_deployment_executions_deployment_id_deployments")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deployment_executions")),
    )
    op.create_index(op.f("ix_deployment_executions_deployment_id"), "deployment_executions", ["deployment_id"])
    op.create_index(op.f("ix_deployment_executions_operation"), "deployment_executions", ["operation"])
    op.create_index(op.f("ix_deployment_executions_status"), "deployment_executions", ["status"])
    op.create_index(op.f("ix_deployment_executions_trigger_source"), "deployment_executions", ["trigger_source"])

    op.create_table(
        "deployment_target_executions",
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("deployment_id", sa.Uuid(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("server_id", sa.Uuid(), nullable=False),
        sa.Column("status", deployment_status, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("revision_id", sa.Uuid(), nullable=True),
        sa.Column("stdout", sa.Text(), nullable=True),
        sa.Column("stderr", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployments.id"], name=op.f("fk_deployment_target_executions_deployment_id_deployments")),
        sa.ForeignKeyConstraint(["execution_id"], ["deployment_executions.id"], name=op.f("fk_deployment_target_executions_execution_id_deployment_executions")),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_deployment_target_executions_job_id_jobs")),
        sa.ForeignKeyConstraint(["revision_id"], ["deployment_revisions.id"], name=op.f("fk_deployment_target_executions_revision_id_deployment_revisions")),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], name=op.f("fk_deployment_target_executions_server_id_servers")),
        sa.ForeignKeyConstraint(["target_id"], ["deployment_targets.id"], name=op.f("fk_deployment_target_executions_target_id_deployment_targets")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deployment_target_executions")),
    )
    op.create_index(op.f("ix_deployment_target_executions_deployment_id"), "deployment_target_executions", ["deployment_id"])
    op.create_index(op.f("ix_deployment_target_executions_execution_id"), "deployment_target_executions", ["execution_id"])
    op.create_index(op.f("ix_deployment_target_executions_server_id"), "deployment_target_executions", ["server_id"])
    op.create_index(op.f("ix_deployment_target_executions_status"), "deployment_target_executions", ["status"])
    op.create_index(op.f("ix_deployment_target_executions_target_id"), "deployment_target_executions", ["target_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_deployment_target_executions_target_id"), table_name="deployment_target_executions")
    op.drop_index(op.f("ix_deployment_target_executions_status"), table_name="deployment_target_executions")
    op.drop_index(op.f("ix_deployment_target_executions_server_id"), table_name="deployment_target_executions")
    op.drop_index(op.f("ix_deployment_target_executions_execution_id"), table_name="deployment_target_executions")
    op.drop_index(op.f("ix_deployment_target_executions_deployment_id"), table_name="deployment_target_executions")
    op.drop_table("deployment_target_executions")
    op.drop_index(op.f("ix_deployment_executions_trigger_source"), table_name="deployment_executions")
    op.drop_index(op.f("ix_deployment_executions_status"), table_name="deployment_executions")
    op.drop_index(op.f("ix_deployment_executions_operation"), table_name="deployment_executions")
    op.drop_index(op.f("ix_deployment_executions_deployment_id"), table_name="deployment_executions")
    op.drop_table("deployment_executions")
