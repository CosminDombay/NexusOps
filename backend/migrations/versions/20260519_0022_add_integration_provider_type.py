"""add integration provider type

Revision ID: 20260519_0022
Revises: 20260519_0021
Create Date: 2026-05-19 21:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260519_0022"
down_revision: str | None = "20260519_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    provider_type = postgresql.ENUM(
        "proxmox",
        "prometheus",
        "grafana",
        "loki",
        "tailscale",
        "custom",
        name="integration_provider_type",
    )
    provider_type.create(op.get_bind(), checkfirst=True)
    provider_type_column = postgresql.ENUM(
        "proxmox",
        "prometheus",
        "grafana",
        "loki",
        "tailscale",
        "custom",
        name="integration_provider_type",
        create_type=False,
    )
    op.add_column(
        "integrations",
        sa.Column(
            "provider_type",
            provider_type_column,
            nullable=False,
            server_default="custom",
        ),
    )
    op.create_index(op.f("ix_integrations_provider_type"), "integrations", ["provider_type"], unique=False)
    op.execute(
        """
        UPDATE integrations
        SET provider_type = (CASE
            WHEN lower(name) LIKE '%proxmox%' THEN 'proxmox'
            WHEN lower(name) LIKE '%prometheus%' THEN 'prometheus'
            WHEN lower(name) LIKE '%grafana%' THEN 'grafana'
            WHEN lower(name) LIKE '%loki%' THEN 'loki'
            WHEN lower(name) LIKE '%tailscale%' THEN 'tailscale'
            WHEN type = 'infrastructure_provider' THEN 'proxmox'
            WHEN type = 'networking' THEN 'tailscale'
            ELSE 'custom'
        END)::integration_provider_type
        """
    )
    op.alter_column("integrations", "provider_type", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_integrations_provider_type"), table_name="integrations")
    op.drop_column("integrations", "provider_type")
    sa.Enum(name="integration_provider_type").drop(op.get_bind(), checkfirst=True)
