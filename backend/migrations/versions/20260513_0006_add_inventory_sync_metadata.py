"""add inventory sync metadata

Revision ID: 20260513_0006
Revises: 20260513_0005
Create Date: 2026-05-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260513_0006"
down_revision: str | None = "20260513_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

inventory_lifecycle_state = postgresql.ENUM(
    "discovered",
    "managed",
    "provisioned",
    "unmanaged",
    "archived",
    name="inventory_lifecycle_state",
    create_type=False,
)
inventory_sync_status = postgresql.ENUM(
    "unknown",
    "synced",
    "unmanaged",
    "orphaned",
    "mismatch",
    "archived",
    name="inventory_sync_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    inventory_lifecycle_state.create(bind, checkfirst=True)
    inventory_sync_status.create(bind, checkfirst=True)

    op.add_column("servers", sa.Column("external_id", sa.String(length=100), nullable=True))
    op.add_column(
        "servers",
        sa.Column("source", sa.String(length=100), server_default="manual", nullable=False),
    )
    op.add_column(
        "servers",
        sa.Column("managed", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column(
        "servers",
        sa.Column(
            "lifecycle_state",
            inventory_lifecycle_state,
            server_default="managed",
            nullable=False,
        ),
    )
    op.add_column(
        "servers",
        sa.Column(
            "sync_status",
            inventory_sync_status,
            server_default="unknown",
            nullable=False,
        ),
    )
    op.add_column("servers", sa.Column("provider_node", sa.String(length=100), nullable=True))
    op.add_column("servers", sa.Column("provider_type", sa.String(length=50), nullable=True))
    op.add_column(
        "servers",
        sa.Column("provider_metadata", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
    )
    op.add_column("servers", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_servers_external_id", "servers", ["external_id"])
    op.create_index("ix_servers_source", "servers", ["source"])
    op.create_index("ix_servers_managed", "servers", ["managed"])
    op.create_index("ix_servers_lifecycle_state", "servers", ["lifecycle_state"])
    op.create_index("ix_servers_sync_status", "servers", ["sync_status"])
    op.alter_column("servers", "source", server_default=None)
    op.alter_column("servers", "managed", server_default=None)
    op.alter_column("servers", "lifecycle_state", server_default=None)
    op.alter_column("servers", "sync_status", server_default=None)
    op.alter_column("servers", "provider_metadata", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_servers_sync_status", table_name="servers")
    op.drop_index("ix_servers_lifecycle_state", table_name="servers")
    op.drop_index("ix_servers_managed", table_name="servers")
    op.drop_index("ix_servers_source", table_name="servers")
    op.drop_index("ix_servers_external_id", table_name="servers")
    op.drop_column("servers", "last_seen_at")
    op.drop_column("servers", "provider_metadata")
    op.drop_column("servers", "provider_type")
    op.drop_column("servers", "provider_node")
    op.drop_column("servers", "sync_status")
    op.drop_column("servers", "lifecycle_state")
    op.drop_column("servers", "managed")
    op.drop_column("servers", "source")
    op.drop_column("servers", "external_id")

    bind = op.get_bind()
    inventory_sync_status.drop(bind, checkfirst=True)
    inventory_lifecycle_state.drop(bind, checkfirst=True)
