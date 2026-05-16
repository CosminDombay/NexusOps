from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from backend.app.core.config import settings
from backend.app.db.base import Base
from backend.app.modules.deployments.models import Deployment, DeploymentRevision, DeploymentTarget
from backend.app.modules.execution.models import CommandExecution
from backend.app.modules.inventory.models import Server
from backend.app.modules.integrations.models import Integration
from backend.app.modules.identity.models import (
    IdentityExecution,
    LinuxGroup,
    LinuxUser,
    PermissionTemplate,
    SSHKey,
)
from backend.app.modules.jobs.models import Job
from backend.app.modules.monitoring.models import MetricSample
from backend.app.modules.packages.models import PackageDefinitionRecord, PackageInstallation
from backend.app.modules.profiles.models import InfrastructureProfileRecord, StandardizationProfile
from backend.app.modules.provisioning.models import ProvisioningRequest, VirtualMachine

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

_models = (
    CommandExecution,
    Deployment,
    DeploymentRevision,
    DeploymentTarget,
    IdentityExecution,
    Integration,
    Job,
    LinuxGroup,
    LinuxUser,
    MetricSample,
    PackageDefinitionRecord,
    PackageInstallation,
    PermissionTemplate,
    InfrastructureProfileRecord,
    ProvisioningRequest,
    Server,
    StandardizationProfile,
    SSHKey,
    VirtualMachine,
)


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio

    asyncio.run(run_migrations_online())
