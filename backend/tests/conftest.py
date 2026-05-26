from collections.abc import AsyncGenerator, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.db.base import Base
from backend.app.db.session import get_db_session
from backend.app.main import app
from backend.app.core.config import settings
from backend.app.modules.auth.models import User, UserRole
from backend.app.modules.auth.security.dependencies import get_current_user
from backend.app.modules.auth.security.hashing import hash_password
from backend.app.modules.inventory.models import Server

_models = (Server, User)


def _build_test_client(
    tmp_path,
    *,
    bypass_auth: bool,
    seed_auth_users: bool = False,
) -> Generator[TestClient, None, None]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'nexusops-test.db'}"
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    async def override_get_current_user() -> User:
        return User(
            username="test-admin",
            email="test-admin@example.com",
            password_hash="not-used",
            role=UserRole.ADMIN,
            is_active=True,
            is_superuser=True,
        )

    async def create_schema() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        if seed_auth_users:
            async with session_factory() as session:
                session.add_all(
                    [
                        User(
                            username="admin",
                            email="admin@example.com",
                            password_hash=hash_password("Password123!"),
                            role=UserRole.ADMIN,
                            is_active=True,
                            is_superuser=True,
                        ),
                        User(
                            username="operator",
                            email="operator@example.com",
                            password_hash=hash_password("Password123!"),
                            role=UserRole.OPERATOR,
                            is_active=True,
                            is_superuser=False,
                        ),
                        User(
                            username="viewer",
                            email="viewer@example.com",
                            password_hash=hash_password("Password123!"),
                            role=UserRole.VIEWER,
                            is_active=True,
                            is_superuser=False,
                        ),
                    ]
                )
                await session.commit()

    async def drop_schema() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    import asyncio

    asyncio.run(create_schema())
    app.dependency_overrides[get_db_session] = override_get_db_session
    if bypass_auth:
        app.dependency_overrides[get_current_user] = override_get_current_user

    previous_rate_limit_enabled = settings.rate_limit_enabled
    previous_runtime_refresh_enabled = settings.runtime_refresh_enabled
    settings.rate_limit_enabled = False
    settings.runtime_refresh_enabled = False
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        settings.rate_limit_enabled = previous_rate_limit_enabled
        settings.runtime_refresh_enabled = previous_runtime_refresh_enabled
        app.dependency_overrides.clear()
        asyncio.run(drop_schema())


@pytest.fixture()
def client(tmp_path) -> Generator[TestClient, None, None]:
    yield from _build_test_client(tmp_path, bypass_auth=True)


@pytest.fixture()
def unauthenticated_client(tmp_path) -> Generator[TestClient, None, None]:
    yield from _build_test_client(tmp_path, bypass_auth=False)


@pytest.fixture()
def auth_client(tmp_path) -> Generator[TestClient, None, None]:
    yield from _build_test_client(tmp_path, bypass_auth=False, seed_auth_users=True)
