"""create automations

Revision ID: 20260517_0016
Revises: 20260517_0015
Create Date: 2026-05-17 12:15:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260517_0016"
down_revision: str | None = "20260517_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    schedule_type = sa.Enum("interval", "cron", name="automation_schedule_type")
    target_mode = sa.Enum("single_host", "multiple_hosts", name="automation_target_mode")
    operation_type = sa.Enum("action", "profile", "package", "deployment", "command", name="automation_operation_type")
    op.create_table(
        "automations",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("schedule_type", schedule_type, nullable=False),
        sa.Column("cron_expression", sa.String(length=120), nullable=True),
        sa.Column("interval_seconds", sa.Integer(), nullable=True),
        sa.Column("target_mode", target_mode, nullable=False),
        sa.Column("target_server_ids", sa.JSON(), nullable=False),
        sa.Column("operation_type", operation_type, nullable=False),
        sa.Column("reference_id", sa.String(length=255), nullable=True),
        sa.Column("raw_command", sa.Text(), nullable=True),
        sa.Column("variables_json", sa.JSON(), nullable=False),
        sa.Column("credential_refs", sa.JSON(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=50), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_automations")),
    )
    op.create_index(op.f("ix_automations_enabled"), "automations", ["enabled"], unique=False)
    op.create_index(op.f("ix_automations_name"), "automations", ["name"], unique=False)
    op.create_index(op.f("ix_automations_operation_type"), "automations", ["operation_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_automations_operation_type"), table_name="automations")
    op.drop_index(op.f("ix_automations_name"), table_name="automations")
    op.drop_index(op.f("ix_automations_enabled"), table_name="automations")
    op.drop_table("automations")
    sa.Enum(name="automation_operation_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="automation_target_mode").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="automation_schedule_type").drop(op.get_bind(), checkfirst=True)
