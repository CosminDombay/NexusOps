"""create jobs table

Revision ID: 20260513_0002
Revises: 20260512_0001
Create Date: 2026-05-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260513_0002"
down_revision: Union[str, None] = "20260512_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

job_status = postgresql.ENUM(
    "pending",
    "running",
    "success",
    "failed",
    "cancelled",
    name="job_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    job_status.create(bind, checkfirst=True)

    op.create_table(
        "jobs",
        sa.Column("target_server_id", sa.Uuid(), nullable=False),
        sa.Column("operation_type", sa.String(length=100), nullable=False),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("status", job_status, nullable=False),
        sa.Column("stdout", sa.Text(), nullable=True),
        sa.Column("stderr", sa.Text(), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["target_server_id"],
            ["servers.id"],
            name=op.f("fk_jobs_target_server_id_servers"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
    )
    op.create_index(op.f("ix_jobs_created_at"), "jobs", ["created_at"], unique=False)
    op.create_index(op.f("ix_jobs_operation_type"), "jobs", ["operation_type"], unique=False)
    op.create_index(op.f("ix_jobs_status"), "jobs", ["status"], unique=False)
    op.create_index(op.f("ix_jobs_target_server_id"), "jobs", ["target_server_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_jobs_target_server_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_status"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_operation_type"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_created_at"), table_name="jobs")
    op.drop_table("jobs")

    bind = op.get_bind()
    job_status.drop(bind, checkfirst=True)
