"""integration authority sync state

Revision ID: 20260523_0028
Revises: 20260521_0027
Create Date: 2026-05-23 14:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260523_0028"
down_revision: str | None = "20260521_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE inventory_sync_status ADD VALUE IF NOT EXISTS 'stale'")
        op.execute("ALTER TYPE inventory_sync_status ADD VALUE IF NOT EXISTS 'disconnected'")

    integration_state = sa.Enum(
        "connected",
        "disconnected",
        "error",
        "disabled",
        "syncing",
        name="integration_state",
    )
    integration_state.create(bind, checkfirst=True)

    op.add_column(
        "integrations",
        sa.Column(
            "state",
            integration_state,
            nullable=False,
            server_default="disabled",
        ),
    )
    op.add_column("integrations", sa.Column("last_successful_sync", sa.DateTime(timezone=True), nullable=True))
    op.add_column("integrations", sa.Column("last_error", sa.Text(), nullable=True))
    op.create_index(op.f("ix_integrations_state"), "integrations", ["state"])
    if bind.dialect.name == "postgresql":
        op.execute(
            "UPDATE integrations "
            "SET state = CASE "
            "WHEN enabled THEN 'disconnected'::integration_state "
            "ELSE 'disabled'::integration_state "
            "END"
        )
    else:
        op.execute("UPDATE integrations SET state = CASE WHEN enabled THEN 'disconnected' ELSE 'disabled' END")
    op.alter_column("integrations", "state", server_default=None)

    op.add_column("servers", sa.Column("integration_id", sa.Uuid(), nullable=True))
    op.add_column("servers", sa.Column("source_type", sa.String(length=100), nullable=False, server_default="manual"))
    op.add_column("servers", sa.Column("sync_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("servers", sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("servers", sa.Column("stale_since", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        op.f("fk_servers_integration_id_integrations"),
        "servers",
        "integrations",
        ["integration_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_servers_integration_id"), "servers", ["integration_id"])
    op.create_index(op.f("ix_servers_source_type"), "servers", ["source_type"])
    op.alter_column("servers", "source_type", server_default=None)
    op.alter_column("servers", "sync_metadata", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_servers_source_type"), table_name="servers")
    op.drop_index(op.f("ix_servers_integration_id"), table_name="servers")
    op.drop_constraint(op.f("fk_servers_integration_id_integrations"), "servers", type_="foreignkey")
    op.drop_column("servers", "stale_since")
    op.drop_column("servers", "last_sync_at")
    op.drop_column("servers", "sync_metadata")
    op.drop_column("servers", "source_type")
    op.drop_column("servers", "integration_id")
    op.drop_index(op.f("ix_integrations_state"), table_name="integrations")
    op.drop_column("integrations", "last_error")
    op.drop_column("integrations", "last_successful_sync")
    op.drop_column("integrations", "state")

    bind = op.get_bind()
    sa.Enum(
        "connected",
        "disconnected",
        "error",
        "disabled",
        "syncing",
        name="integration_state",
    ).drop(bind, checkfirst=True)
