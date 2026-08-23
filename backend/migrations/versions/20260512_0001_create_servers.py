"""create servers table

Revision ID: 20260512_0001
Revises:
Create Date: 2026-05-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260512_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

server_environment = postgresql.ENUM(
    "DEVELOPMENT",
    "STAGING",
    "PRODUCTION",
    "TESTING",
    "LAB",
    name="server_environment",
    create_type=False,
)
server_status = postgresql.ENUM(
    "UNKNOWN",
    "ONLINE",
    "OFFLINE",
    "MAINTENANCE",
    name="serverstatus",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    server_environment.create(bind, checkfirst=True)
    server_status.create(bind, checkfirst=True)

    op.create_table(
        "servers",
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=False),
        sa.Column("operating_system", sa.String(length=150), nullable=False),
        sa.Column("vmid", sa.String(length=100), nullable=True),
        sa.Column("environment", server_environment, nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("ssh_port", sa.Integer(), nullable=False),
        sa.Column("ssh_username", sa.String(length=100), nullable=False),
        sa.Column("status", server_status, nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_servers")),
        sa.UniqueConstraint("hostname", name="uq_servers_hostname"),
        sa.UniqueConstraint("ip_address", name="uq_servers_ip_address"),
    )
    op.create_index(op.f("ix_servers_created_at"), "servers", ["created_at"], unique=False)
    op.create_index(op.f("ix_servers_environment"), "servers", ["environment"], unique=False)
    op.create_index(op.f("ix_servers_hostname"), "servers", ["hostname"], unique=False)
    op.create_index(op.f("ix_servers_ip_address"), "servers", ["ip_address"], unique=False)
    op.create_index(op.f("ix_servers_provider"), "servers", ["provider"], unique=False)
    op.create_index(op.f("ix_servers_vmid"), "servers", ["vmid"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_servers_vmid"), table_name="servers")
    op.drop_index(op.f("ix_servers_provider"), table_name="servers")
    op.drop_index(op.f("ix_servers_ip_address"), table_name="servers")
    op.drop_index(op.f("ix_servers_hostname"), table_name="servers")
    op.drop_index(op.f("ix_servers_environment"), table_name="servers")
    op.drop_index(op.f("ix_servers_created_at"), table_name="servers")
    op.drop_table("servers")

    bind = op.get_bind()
    server_status.drop(bind, checkfirst=True)
    server_environment.drop(bind, checkfirst=True)
