"""deployment definition remote path

Revision ID: 20260625_0043
Revises: 20260620_0042
Create Date: 2026-06-25 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260625_0043"
down_revision: str | None = "20260620_0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "deployments",
        sa.Column(
            "remote_path",
            sa.String(length=500),
            nullable=False,
            server_default="/opt/nexusops/deployments",
        ),
    )
    op.execute(
        """
        UPDATE deployments
        SET remote_path = first_target.remote_path
        FROM (
            SELECT DISTINCT ON (deployment_id) deployment_id, remote_path
            FROM deployment_targets
            ORDER BY deployment_id, created_at ASC
        ) AS first_target
        WHERE deployments.id = first_target.deployment_id
        """
    )
    op.alter_column("deployments", "remote_path", server_default=None)


def downgrade() -> None:
    op.drop_column("deployments", "remote_path")
