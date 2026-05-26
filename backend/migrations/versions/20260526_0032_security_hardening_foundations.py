"""security hardening foundations

Revision ID: 20260526_0032
Revises: 20260523_0031
Create Date: 2026-05-26 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260526_0032"
down_revision: str | None = "20260523_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "refresh_token_sessions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_id", sa.String(length=64), nullable=False),
        sa.Column("family_id", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("source_ip", sa.String(length=64), nullable=True),
        sa.Column("revoke_reason", sa.String(length=120), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_id", name="uq_refresh_token_sessions_token_id"),
    )
    op.create_index("ix_refresh_token_sessions_user_family", "refresh_token_sessions", ["user_id", "family_id"], unique=False)
    op.create_index(op.f("ix_refresh_token_sessions_user_id"), "refresh_token_sessions", ["user_id"], unique=False)
    op.create_index(op.f("ix_refresh_token_sessions_token_id"), "refresh_token_sessions", ["token_id"], unique=False)
    op.create_index(op.f("ix_refresh_token_sessions_family_id"), "refresh_token_sessions", ["family_id"], unique=False)
    op.create_index(op.f("ix_refresh_token_sessions_expires_at"), "refresh_token_sessions", ["expires_at"], unique=False)
    op.create_index(op.f("ix_refresh_token_sessions_revoked_at"), "refresh_token_sessions", ["revoked_at"], unique=False)

    op.create_table(
        "remote_access_tokens",
        sa.Column("token_id", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("server_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=True),
        sa.Column("operation", sa.String(length=50), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_ip", sa.String(length=64), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["refresh_token_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_id", name="uq_remote_access_tokens_token_id"),
    )
    op.create_index("ix_remote_access_tokens_scope", "remote_access_tokens", ["user_id", "server_id", "operation"], unique=False)
    op.create_index(op.f("ix_remote_access_tokens_token_id"), "remote_access_tokens", ["token_id"], unique=False)
    op.create_index(op.f("ix_remote_access_tokens_user_id"), "remote_access_tokens", ["user_id"], unique=False)
    op.create_index(op.f("ix_remote_access_tokens_server_id"), "remote_access_tokens", ["server_id"], unique=False)
    op.create_index(op.f("ix_remote_access_tokens_session_id"), "remote_access_tokens", ["session_id"], unique=False)
    op.create_index(op.f("ix_remote_access_tokens_operation"), "remote_access_tokens", ["operation"], unique=False)
    op.create_index(op.f("ix_remote_access_tokens_expires_at"), "remote_access_tokens", ["expires_at"], unique=False)
    op.create_index(op.f("ix_remote_access_tokens_consumed_at"), "remote_access_tokens", ["consumed_at"], unique=False)

    op.add_column("servers", sa.Column("trusted_ssh_host_key_sha256", sa.String(length=95), nullable=True))
    op.add_column("servers", sa.Column("trusted_ssh_host_key_accepted_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("jobs", sa.Column("actual_command", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("command_display", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("command_policy", sa.String(length=50), nullable=False, server_default="allowed"))
    op.add_column("jobs", sa.Column("command_hash", sa.String(length=64), nullable=True))
    op.add_column("jobs", sa.Column("initiated_by_user_id", sa.Uuid(), nullable=True))
    op.add_column("jobs", sa.Column("initiated_by_username", sa.String(length=255), nullable=True))
    op.create_foreign_key("fk_jobs_initiated_by_user_id_users", "jobs", "users", ["initiated_by_user_id"], ["id"], ondelete="SET NULL")
    op.create_index(op.f("ix_jobs_command_policy"), "jobs", ["command_policy"], unique=False)
    op.create_index(op.f("ix_jobs_initiated_by_user_id"), "jobs", ["initiated_by_user_id"], unique=False)
    op.create_index("ix_jobs_status_created_at", "jobs", ["status", "created_at"], unique=False)
    op.create_index("ix_jobs_target_status", "jobs", ["target_server_id", "status"], unique=False)

    op.create_table(
        "job_execution_events",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_execution_events_job_created", "job_execution_events", ["job_id", "created_at"], unique=False)
    op.create_index("ix_job_execution_events_correlation", "job_execution_events", ["correlation_id"], unique=False)
    op.create_index(op.f("ix_job_execution_events_job_id"), "job_execution_events", ["job_id"], unique=False)
    op.create_index(op.f("ix_job_execution_events_event_type"), "job_execution_events", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_job_execution_events_event_type"), table_name="job_execution_events")
    op.drop_index(op.f("ix_job_execution_events_job_id"), table_name="job_execution_events")
    op.drop_index("ix_job_execution_events_correlation", table_name="job_execution_events")
    op.drop_index("ix_job_execution_events_job_created", table_name="job_execution_events")
    op.drop_table("job_execution_events")
    op.drop_index("ix_jobs_target_status", table_name="jobs")
    op.drop_index("ix_jobs_status_created_at", table_name="jobs")
    op.drop_index(op.f("ix_jobs_initiated_by_user_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_command_policy"), table_name="jobs")
    op.drop_constraint("fk_jobs_initiated_by_user_id_users", "jobs", type_="foreignkey")
    op.drop_column("jobs", "initiated_by_username")
    op.drop_column("jobs", "initiated_by_user_id")
    op.drop_column("jobs", "command_hash")
    op.drop_column("jobs", "command_policy")
    op.drop_column("jobs", "command_display")
    op.drop_column("jobs", "actual_command")
    op.drop_column("servers", "trusted_ssh_host_key_accepted_at")
    op.drop_column("servers", "trusted_ssh_host_key_sha256")
    op.drop_index(op.f("ix_remote_access_tokens_consumed_at"), table_name="remote_access_tokens")
    op.drop_index(op.f("ix_remote_access_tokens_expires_at"), table_name="remote_access_tokens")
    op.drop_index(op.f("ix_remote_access_tokens_operation"), table_name="remote_access_tokens")
    op.drop_index(op.f("ix_remote_access_tokens_session_id"), table_name="remote_access_tokens")
    op.drop_index(op.f("ix_remote_access_tokens_server_id"), table_name="remote_access_tokens")
    op.drop_index(op.f("ix_remote_access_tokens_user_id"), table_name="remote_access_tokens")
    op.drop_index(op.f("ix_remote_access_tokens_token_id"), table_name="remote_access_tokens")
    op.drop_index("ix_remote_access_tokens_scope", table_name="remote_access_tokens")
    op.drop_table("remote_access_tokens")
    op.drop_index(op.f("ix_refresh_token_sessions_revoked_at"), table_name="refresh_token_sessions")
    op.drop_index(op.f("ix_refresh_token_sessions_expires_at"), table_name="refresh_token_sessions")
    op.drop_index(op.f("ix_refresh_token_sessions_family_id"), table_name="refresh_token_sessions")
    op.drop_index(op.f("ix_refresh_token_sessions_token_id"), table_name="refresh_token_sessions")
    op.drop_index(op.f("ix_refresh_token_sessions_user_id"), table_name="refresh_token_sessions")
    op.drop_index("ix_refresh_token_sessions_user_family", table_name="refresh_token_sessions")
    op.drop_table("refresh_token_sessions")
