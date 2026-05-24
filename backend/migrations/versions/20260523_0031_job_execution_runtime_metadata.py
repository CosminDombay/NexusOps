"""job execution runtime metadata

Revision ID: 20260523_0031
Revises: 20260523_0030
Create Date: 2026-05-23 23:45:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260523_0031"
down_revision: str | None = "20260523_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for value in ("queued", "dispatched", "completed", "stale"):
            op.execute(f"ALTER TYPE job_status ADD VALUE IF NOT EXISTS '{value}'")

    op.add_column("jobs", sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("runtime_duration_seconds", sa.Integer(), nullable=True))
    op.add_column("jobs", sa.Column("execution_origin", sa.String(length=100), nullable=False, server_default="manual"))
    op.add_column("jobs", sa.Column("correlation_id", sa.String(length=100), nullable=True))
    op.add_column("jobs", sa.Column("cancellation_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("runtime_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("jobs", sa.Column("output_events", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.create_index(op.f("ix_jobs_correlation_id"), "jobs", ["correlation_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_jobs_correlation_id"), table_name="jobs")
    op.drop_column("jobs", "output_events")
    op.drop_column("jobs", "runtime_metadata")
    op.drop_column("jobs", "cancellation_requested_at")
    op.drop_column("jobs", "correlation_id")
    op.drop_column("jobs", "execution_origin")
    op.drop_column("jobs", "runtime_duration_seconds")
    op.drop_column("jobs", "dispatched_at")
    op.drop_column("jobs", "queued_at")
