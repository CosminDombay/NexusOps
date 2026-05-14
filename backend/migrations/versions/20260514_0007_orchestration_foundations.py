"""add health deployments and monitoring foundations

Revision ID: 20260514_0007
Revises: 20260513_0006
Create Date: 2026-05-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260514_0007"
down_revision: Union[str, None] = "20260513_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

inventory_health_status = postgresql.ENUM(
    "online",
    "unreachable",
    "unknown",
    "provisioning",
    "archived",
    "sync_error",
    name="inventory_health_status",
    create_type=False,
)
deployment_status = postgresql.ENUM(
    "draft",
    "deploying",
    "running",
    "stopped",
    "failed",
    name="deployment_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    inventory_health_status.create(bind, checkfirst=True)
    deployment_status.create(bind, checkfirst=True)

    op.add_column("servers", sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "servers",
        sa.Column("last_health_status", inventory_health_status, server_default="unknown", nullable=False),
    )
    op.add_column("servers", sa.Column("last_health_error", sa.String(length=500), nullable=True))
    op.create_index("ix_servers_last_health_status", "servers", ["last_health_status"])
    op.alter_column("servers", "last_health_status", server_default=None)

    op.create_table(
        "deployments",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("compose_content", sa.Text(), nullable=False),
        sa.Column("env_content", sa.Text(), nullable=True),
        sa.Column("status", deployment_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deployments")),
    )
    op.create_index(op.f("ix_deployments_name"), "deployments", ["name"])
    op.create_index(op.f("ix_deployments_status"), "deployments", ["status"])

    op.create_table(
        "deployment_targets",
        sa.Column("deployment_id", sa.Uuid(), nullable=False),
        sa.Column("server_id", sa.Uuid(), nullable=False),
        sa.Column("remote_path", sa.String(length=500), nullable=False),
        sa.Column("status", deployment_status, nullable=False),
        sa.Column("last_job_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployments.id"], name=op.f("fk_deployment_targets_deployment_id_deployments")),
        sa.ForeignKeyConstraint(["last_job_id"], ["jobs.id"], name=op.f("fk_deployment_targets_last_job_id_jobs")),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], name=op.f("fk_deployment_targets_server_id_servers")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deployment_targets")),
    )
    op.create_index(op.f("ix_deployment_targets_deployment_id"), "deployment_targets", ["deployment_id"])
    op.create_index(op.f("ix_deployment_targets_server_id"), "deployment_targets", ["server_id"])
    op.create_index(op.f("ix_deployment_targets_status"), "deployment_targets", ["status"])

    op.create_table(
        "deployment_revisions",
        sa.Column("deployment_id", sa.Uuid(), nullable=False),
        sa.Column("server_id", sa.Uuid(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(length=50), nullable=False),
        sa.Column("compose_content", sa.Text(), nullable=False),
        sa.Column("env_content", sa.Text(), nullable=True),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("status", deployment_status, nullable=False),
        sa.Column("stdout", sa.Text(), nullable=True),
        sa.Column("stderr", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployments.id"], name=op.f("fk_deployment_revisions_deployment_id_deployments")),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_deployment_revisions_job_id_jobs")),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], name=op.f("fk_deployment_revisions_server_id_servers")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deployment_revisions")),
    )
    op.create_index(op.f("ix_deployment_revisions_deployment_id"), "deployment_revisions", ["deployment_id"])
    op.create_index(op.f("ix_deployment_revisions_operation"), "deployment_revisions", ["operation"])
    op.create_index(op.f("ix_deployment_revisions_server_id"), "deployment_revisions", ["server_id"])
    op.create_index(op.f("ix_deployment_revisions_status"), "deployment_revisions", ["status"])

    op.create_table(
        "metric_samples",
        sa.Column("server_id", sa.Uuid(), nullable=False),
        sa.Column("metric_name", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], name=op.f("fk_metric_samples_server_id_servers")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_metric_samples")),
    )
    op.create_index(op.f("ix_metric_samples_collected_at"), "metric_samples", ["collected_at"])
    op.create_index(op.f("ix_metric_samples_metric_name"), "metric_samples", ["metric_name"])
    op.create_index(op.f("ix_metric_samples_server_id"), "metric_samples", ["server_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_metric_samples_server_id"), table_name="metric_samples")
    op.drop_index(op.f("ix_metric_samples_metric_name"), table_name="metric_samples")
    op.drop_index(op.f("ix_metric_samples_collected_at"), table_name="metric_samples")
    op.drop_table("metric_samples")

    op.drop_index(op.f("ix_deployment_revisions_status"), table_name="deployment_revisions")
    op.drop_index(op.f("ix_deployment_revisions_server_id"), table_name="deployment_revisions")
    op.drop_index(op.f("ix_deployment_revisions_operation"), table_name="deployment_revisions")
    op.drop_index(op.f("ix_deployment_revisions_deployment_id"), table_name="deployment_revisions")
    op.drop_table("deployment_revisions")

    op.drop_index(op.f("ix_deployment_targets_status"), table_name="deployment_targets")
    op.drop_index(op.f("ix_deployment_targets_server_id"), table_name="deployment_targets")
    op.drop_index(op.f("ix_deployment_targets_deployment_id"), table_name="deployment_targets")
    op.drop_table("deployment_targets")

    op.drop_index(op.f("ix_deployments_status"), table_name="deployments")
    op.drop_index(op.f("ix_deployments_name"), table_name="deployments")
    op.drop_table("deployments")

    op.drop_index("ix_servers_last_health_status", table_name="servers")
    op.drop_column("servers", "last_health_error")
    op.drop_column("servers", "last_health_status")
    op.drop_column("servers", "last_health_check_at")

    bind = op.get_bind()
    deployment_status.drop(bind, checkfirst=True)
    inventory_health_status.drop(bind, checkfirst=True)
