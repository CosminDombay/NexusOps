"""credentials variables and inventory credential links

Revision ID: 20260516_0011
Revises: 20260516_0010
Create Date: 2026-05-16 19:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260516_0011"
down_revision: str | None = "20260516_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE credential_type AS ENUM ('password', 'ssh_password', 'ssh_key', 'api_token', 'env_secret');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE credential_scope AS ENUM ('global', 'project', 'environment');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    credential_type = postgresql.ENUM(
        "password",
        "ssh_password",
        "ssh_key",
        "api_token",
        "env_secret",
        name="credential_type",
        create_type=False,
    )
    credential_scope = postgresql.ENUM("global", "project", "environment", name="credential_scope", create_type=False)

    op.create_table(
        "credentials",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("credential_type", credential_type, nullable=False),
        sa.Column("username", sa.String(length=100), nullable=True),
        sa.Column("encrypted_secret", sa.Text(), nullable=True),
        sa.Column("private_key", sa.Text(), nullable=True),
        sa.Column("passphrase", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("scope", credential_scope, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credentials")),
        sa.UniqueConstraint("name", name=op.f("uq_credentials_name")),
    )
    op.create_index(op.f("ix_credentials_credential_type"), "credentials", ["credential_type"], unique=False)
    op.create_index(op.f("ix_credentials_name"), "credentials", ["name"], unique=False)
    op.create_index(op.f("ix_credentials_scope"), "credentials", ["scope"], unique=False)

    op.create_table(
        "credential_usages",
        sa.Column("credential_id", sa.Uuid(), nullable=False),
        sa.Column("used_by_type", sa.String(length=100), nullable=False),
        sa.Column("used_by_id", sa.String(length=100), nullable=False),
        sa.Column("purpose", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["credential_id"], ["credentials.id"], name=op.f("fk_credential_usages_credential_id_credentials"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credential_usages")),
    )
    op.create_index(op.f("ix_credential_usages_credential_id"), "credential_usages", ["credential_id"], unique=False)
    op.create_index(op.f("ix_credential_usages_used_by_id"), "credential_usages", ["used_by_id"], unique=False)
    op.create_index(op.f("ix_credential_usages_used_by_type"), "credential_usages", ["used_by_type"], unique=False)

    op.add_column("servers", sa.Column("credential_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_servers_credential_id"), "servers", ["credential_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_servers_credential_id_credentials"),
        "servers",
        "credentials",
        ["credential_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "variables",
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("is_secret", sa.Boolean(), nullable=False),
        sa.Column("credential_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["credential_id"], ["credentials.id"], name=op.f("fk_variables_credential_id_credentials"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_variables")),
        sa.UniqueConstraint("key", name=op.f("uq_variables_key")),
    )
    op.create_index(op.f("ix_variables_category"), "variables", ["category"], unique=False)
    op.create_index(op.f("ix_variables_credential_id"), "variables", ["credential_id"], unique=False)
    op.create_index(op.f("ix_variables_key"), "variables", ["key"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_variables_key"), table_name="variables")
    op.drop_index(op.f("ix_variables_credential_id"), table_name="variables")
    op.drop_index(op.f("ix_variables_category"), table_name="variables")
    op.drop_table("variables")

    op.drop_constraint(op.f("fk_servers_credential_id_credentials"), "servers", type_="foreignkey")
    op.drop_index(op.f("ix_servers_credential_id"), table_name="servers")
    op.drop_column("servers", "credential_id")

    op.drop_index(op.f("ix_credential_usages_used_by_type"), table_name="credential_usages")
    op.drop_index(op.f("ix_credential_usages_used_by_id"), table_name="credential_usages")
    op.drop_index(op.f("ix_credential_usages_credential_id"), table_name="credential_usages")
    op.drop_table("credential_usages")

    op.drop_index(op.f("ix_credentials_scope"), table_name="credentials")
    op.drop_index(op.f("ix_credentials_name"), table_name="credentials")
    op.drop_index(op.f("ix_credentials_credential_type"), table_name="credentials")
    op.drop_table("credentials")

    sa.Enum(name="credential_scope").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="credential_type").drop(op.get_bind(), checkfirst=True)
