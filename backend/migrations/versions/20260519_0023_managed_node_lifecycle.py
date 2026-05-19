"""managed node lifecycle foundation

Revision ID: 20260519_0023
Revises: 20260519_0022
Create Date: 2026-05-19 22:15:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260519_0023"
down_revision: str | None = "20260519_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE inventory_lifecycle_state ADD VALUE IF NOT EXISTS 'imported'")
    op.execute("ALTER TYPE inventory_lifecycle_state ADD VALUE IF NOT EXISTS 'decommissioned'")

    node_type = postgresql.ENUM(
        "vm",
        "lxc",
        "physical",
        "hypervisor",
        name="managed_node_type",
    )
    node_type.create(op.get_bind(), checkfirst=True)
    node_type_column = postgresql.ENUM(
        "vm",
        "lxc",
        "physical",
        "hypervisor",
        name="managed_node_type",
        create_type=False,
    )

    management_state = postgresql.ENUM(
        "discovered",
        "unmanaged",
        "managed",
        "retired",
        name="management_state",
    )
    management_state.create(op.get_bind(), checkfirst=True)
    management_state_column = postgresql.ENUM(
        "discovered",
        "unmanaged",
        "managed",
        "retired",
        name="management_state",
        create_type=False,
    )

    sync_state_column = postgresql.ENUM(
        "unknown",
        "synced",
        "unmanaged",
        "orphaned",
        "mismatch",
        "archived",
        name="inventory_sync_status",
        create_type=False,
    )

    op.add_column(
        "servers",
        sa.Column("node_type", node_type_column, nullable=False, server_default="physical"),
    )
    op.add_column(
        "servers",
        sa.Column("management_state", management_state_column, nullable=False, server_default="managed"),
    )
    op.add_column(
        "servers",
        sa.Column("sync_state", sync_state_column, nullable=False, server_default="unknown"),
    )
    op.add_column(
        "servers",
        sa.Column("capabilities", sa.JSON(), nullable=False, server_default="[]"),
    )

    op.execute(
        """
        UPDATE servers
        SET
            node_type = (CASE
                WHEN lower(coalesce(provider_type, '')) IN ('lxc', 'ct') THEN 'lxc'
                WHEN lower(coalesce(provider_type, '')) IN ('qemu', 'vm') OR vmid IS NOT NULL THEN 'vm'
                WHEN lower(coalesce(provider, '')) IN ('proxmox') AND vmid IS NULL THEN 'hypervisor'
                ELSE 'physical'
            END)::managed_node_type,
            management_state = (CASE
                WHEN lifecycle_state IN ('archived', 'deleted') THEN 'retired'
                WHEN managed IS TRUE THEN 'managed'
                ELSE 'unmanaged'
            END)::management_state,
            sync_state = sync_status,
            capabilities = CASE
                WHEN capabilities IS NULL THEN '[]'::json
                ELSE capabilities
            END
        """
    )

    op.create_index(op.f("ix_servers_node_type"), "servers", ["node_type"], unique=False)
    op.create_index(op.f("ix_servers_management_state"), "servers", ["management_state"], unique=False)
    op.create_index(op.f("ix_servers_sync_state"), "servers", ["sync_state"], unique=False)
    op.alter_column("servers", "node_type", server_default=None)
    op.alter_column("servers", "management_state", server_default=None)
    op.alter_column("servers", "sync_state", server_default=None)
    op.alter_column("servers", "capabilities", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_servers_sync_state"), table_name="servers")
    op.drop_index(op.f("ix_servers_management_state"), table_name="servers")
    op.drop_index(op.f("ix_servers_node_type"), table_name="servers")
    op.drop_column("servers", "capabilities")
    op.drop_column("servers", "sync_state")
    op.drop_column("servers", "management_state")
    op.drop_column("servers", "node_type")
    sa.Enum(name="management_state").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="managed_node_type").drop(op.get_bind(), checkfirst=True)
