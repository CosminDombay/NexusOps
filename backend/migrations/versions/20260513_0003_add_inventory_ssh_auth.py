"""add inventory ssh auth fields

Revision ID: 20260513_0003
Revises: 20260513_0002
Create Date: 2026-05-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260513_0003"
down_revision: Union[str, None] = "20260513_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

server_ssh_auth_method = postgresql.ENUM(
    "key",
    "password",
    name="server_ssh_auth_method",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    server_ssh_auth_method.create(bind, checkfirst=True)

    op.add_column(
        "servers",
        sa.Column(
            "ssh_auth_method",
            server_ssh_auth_method,
            server_default="key",
            nullable=False,
        ),
    )
    op.add_column("servers", sa.Column("ssh_password", sa.String(length=500), nullable=True))
    op.add_column(
        "servers",
        sa.Column("ssh_private_key_path", sa.String(length=500), nullable=True),
    )
    op.alter_column("servers", "ssh_auth_method", server_default=None)


def downgrade() -> None:
    op.drop_column("servers", "ssh_private_key_path")
    op.drop_column("servers", "ssh_password")
    op.drop_column("servers", "ssh_auth_method")

    bind = op.get_bind()
    server_ssh_auth_method.drop(bind, checkfirst=True)
