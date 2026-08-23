"""create identity orchestration tables

Revision ID: 20260514_0008
Revises: 20260514_0007
Create Date: 2026-05-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260514_0008"
down_revision: str | None = "20260514_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

identity_execution_status = postgresql.ENUM(
    "pending",
    "running",
    "success",
    "failed",
    name="identity_execution_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    identity_execution_status.create(bind, checkfirst=True)

    op.create_table(
        "linux_users",
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("shell", sa.String(length=255), nullable=False),
        sa.Column("home_directory", sa.String(length=500), nullable=False),
        sa.Column("sudo_enabled", sa.Boolean(), nullable=False),
        sa.Column("sudo_nopasswd", sa.Boolean(), nullable=False),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.Column("managed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_linux_users")),
        sa.UniqueConstraint("username", name=op.f("uq_linux_users_username")),
    )
    op.create_index(op.f("ix_linux_users_managed"), "linux_users", ["managed"])
    op.create_index(op.f("ix_linux_users_username"), "linux_users", ["username"])

    op.create_table(
        "linux_groups",
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("managed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_linux_groups")),
        sa.UniqueConstraint("name", name=op.f("uq_linux_groups_name")),
    )
    op.create_index(op.f("ix_linux_groups_managed"), "linux_groups", ["managed"])
    op.create_index(op.f("ix_linux_groups_name"), "linux_groups", ["name"])

    op.create_table(
        "ssh_keys",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ssh_keys")),
    )
    op.create_index(op.f("ix_ssh_keys_name"), "ssh_keys", ["name"])

    op.create_table(
        "permission_templates",
        sa.Column("path", sa.String(length=1000), nullable=False),
        sa.Column("owner", sa.String(length=64), nullable=True),
        sa.Column("group", sa.String(length=64), nullable=True),
        sa.Column("mode", sa.String(length=4), nullable=True),
        sa.Column("recursive", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_permission_templates")),
    )

    op.create_table(
        "identity_executions",
        sa.Column("operation_type", sa.String(length=100), nullable=False),
        sa.Column("target_server_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("status", identity_execution_status, nullable=False),
        sa.Column("stdout", sa.Text(), nullable=True),
        sa.Column("stderr", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_identity_executions_job_id_jobs")),
        sa.ForeignKeyConstraint(["target_server_id"], ["servers.id"], name=op.f("fk_identity_executions_target_server_id_servers")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_identity_executions")),
    )
    op.create_index(op.f("ix_identity_executions_operation_type"), "identity_executions", ["operation_type"])
    op.create_index(op.f("ix_identity_executions_status"), "identity_executions", ["status"])
    op.create_index(op.f("ix_identity_executions_target_server_id"), "identity_executions", ["target_server_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_identity_executions_target_server_id"), table_name="identity_executions")
    op.drop_index(op.f("ix_identity_executions_status"), table_name="identity_executions")
    op.drop_index(op.f("ix_identity_executions_operation_type"), table_name="identity_executions")
    op.drop_table("identity_executions")
    op.drop_table("permission_templates")
    op.drop_index(op.f("ix_ssh_keys_name"), table_name="ssh_keys")
    op.drop_table("ssh_keys")
    op.drop_index(op.f("ix_linux_groups_name"), table_name="linux_groups")
    op.drop_index(op.f("ix_linux_groups_managed"), table_name="linux_groups")
    op.drop_table("linux_groups")
    op.drop_index(op.f("ix_linux_users_username"), table_name="linux_users")
    op.drop_index(op.f("ix_linux_users_managed"), table_name="linux_users")
    op.drop_table("linux_users")

    bind = op.get_bind()
    identity_execution_status.drop(bind, checkfirst=True)
