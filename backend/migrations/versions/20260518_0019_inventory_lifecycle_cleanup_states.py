"""add inventory cleanup lifecycle states

Revision ID: 20260518_0019
Revises: 20260517_0018
Create Date: 2026-05-18 13:10:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260518_0019"
down_revision: str | None = "20260517_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for value in ("deleting", "deleted", "failed"):
            op.execute(f"ALTER TYPE inventory_lifecycle_state ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed cheaply and safely in-place.
    pass
