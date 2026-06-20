"""ordered provisioning bootstrap

Revision ID: 20260620_0041
Revises: 20260618_0040
Create Date: 2026-06-20 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260620_0041"
down_revision: str | None = "20260618_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "provisioning_requests",
        sa.Column("bootstrap_items", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "provisioning_blueprints",
        sa.Column("bootstrap_items", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.execute(
        """
        UPDATE provisioning_requests
        SET bootstrap_items = (
            SELECT COALESCE(json_agg(item), '[]'::json)
            FROM (
                SELECT json_build_object('kind', 'profile', 'reference_id', value) AS item
                FROM json_array_elements_text(bootstrap_profile_ids)
                UNION ALL
                SELECT json_build_object('kind', 'package', 'reference_id', value) AS item
                FROM json_array_elements_text(bootstrap_package_ids)
            ) ordered_items
        )
        WHERE json_array_length(bootstrap_items) = 0
        """
    )
    op.execute(
        """
        UPDATE provisioning_blueprints
        SET bootstrap_items = (
            SELECT COALESCE(json_agg(item), '[]'::json)
            FROM (
                SELECT json_build_object('kind', 'profile', 'reference_id', value) AS item
                FROM json_array_elements_text(bootstrap_profile_ids)
                UNION ALL
                SELECT json_build_object('kind', 'package', 'reference_id', value) AS item
                FROM json_array_elements_text(bootstrap_package_ids)
            ) ordered_items
        )
        WHERE json_array_length(bootstrap_items) = 0
        """
    )
    op.alter_column("provisioning_requests", "bootstrap_items", server_default=None)
    op.alter_column("provisioning_blueprints", "bootstrap_items", server_default=None)


def downgrade() -> None:
    op.drop_column("provisioning_blueprints", "bootstrap_items")
    op.drop_column("provisioning_requests", "bootstrap_items")
