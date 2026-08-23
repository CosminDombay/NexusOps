"""create provisioning requests table

Revision ID: 20260513_0005
Revises: 20260513_0004
Create Date: 2026-05-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260513_0005"
down_revision: str | None = "20260513_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

provisioning_status = postgresql.ENUM(
    "requested",
    "validating_ip",
    "cloning",
    "configuring",
    "starting",
    "waiting_for_ssh",
    "inventory_registration",
    "bootstrap_running",
    "completed",
    "failed",
    name="provisioning_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    provisioning_status.create(bind, checkfirst=True)

    op.create_table(
        "provisioning_requests",
        sa.Column("vm_name", sa.String(length=255), nullable=False),
        sa.Column("target_node", sa.String(length=100), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("new_vm_id", sa.Integer(), nullable=False),
        sa.Column("cpu_cores", sa.Integer(), nullable=False),
        sa.Column("memory_mb", sa.Integer(), nullable=False),
        sa.Column("disk_gb", sa.Integer(), nullable=False),
        sa.Column("network_bridge", sa.String(length=100), nullable=False),
        sa.Column("environment", sa.String(length=100), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_on_boot", sa.Boolean(), nullable=False),
        sa.Column("cloud_init_username", sa.String(length=100), nullable=False),
        sa.Column("cloud_init_password", sa.String(length=500), nullable=True),
        sa.Column("ssh_public_key", sa.Text(), nullable=True),
        sa.Column("static_ip_cidr", sa.String(length=64), nullable=False),
        sa.Column("gateway", sa.String(length=64), nullable=False),
        sa.Column("dns_servers", sa.JSON(), nullable=False),
        sa.Column("status", provisioning_status, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("proxmox_task_ids", sa.JSON(), nullable=False),
        sa.Column("server_id", sa.Uuid(), nullable=True),
        sa.Column("bootstrap_profile_ids", sa.JSON(), nullable=False),
        sa.Column("bootstrap_package_ids", sa.JSON(), nullable=False),
        sa.Column("bootstrap_job_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], name=op.f("fk_provisioning_requests_server_id_servers")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provisioning_requests")),
    )
    op.create_index(op.f("ix_provisioning_requests_created_at"), "provisioning_requests", ["created_at"])
    op.create_index(op.f("ix_provisioning_requests_environment"), "provisioning_requests", ["environment"])
    op.create_index(op.f("ix_provisioning_requests_new_vm_id"), "provisioning_requests", ["new_vm_id"])
    op.create_index(op.f("ix_provisioning_requests_status"), "provisioning_requests", ["status"])
    op.create_index(op.f("ix_provisioning_requests_target_node"), "provisioning_requests", ["target_node"])
    op.create_index(op.f("ix_provisioning_requests_vm_name"), "provisioning_requests", ["vm_name"])


def downgrade() -> None:
    op.drop_index(op.f("ix_provisioning_requests_vm_name"), table_name="provisioning_requests")
    op.drop_index(op.f("ix_provisioning_requests_target_node"), table_name="provisioning_requests")
    op.drop_index(op.f("ix_provisioning_requests_status"), table_name="provisioning_requests")
    op.drop_index(op.f("ix_provisioning_requests_new_vm_id"), table_name="provisioning_requests")
    op.drop_index(op.f("ix_provisioning_requests_environment"), table_name="provisioning_requests")
    op.drop_index(op.f("ix_provisioning_requests_created_at"), table_name="provisioning_requests")
    op.drop_table("provisioning_requests")

    bind = op.get_bind()
    provisioning_status.drop(bind, checkfirst=True)
