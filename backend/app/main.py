from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.router import api_v1_router
from backend.app.core.config import settings
from backend.app.core.logging import configure_logging
from backend.app.db.session import AsyncSessionLocal, get_db_session
from backend.app.modules.auth.repositories.user_repository import UserRepository
from backend.app.modules.auth.services.auth_service import AuthService
from backend.app.workers.scheduler.service import scheduler_service


def create_app() -> FastAPI:
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        scheduler_enabled = get_db_session not in app.dependency_overrides
        if scheduler_enabled:
            await bootstrap_admin()
        if scheduler_enabled:
            await scheduler_service.start()
        try:
            yield
        finally:
            if scheduler_enabled:
                await scheduler_service.shutdown()

    app = FastAPI(
        title="NexusOps API",
        version="0.1.0",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()


async def bootstrap_admin() -> None:
    if not (
        settings.nexusops_admin_user
        and settings.nexusops_admin_email
        and settings.nexusops_admin_password
    ):
        return

    async with AsyncSessionLocal() as session:
        service = AuthService(repository=UserRepository(session))
        await service.create_admin_if_missing(
            username=settings.nexusops_admin_user,
            email=settings.nexusops_admin_email,
            password=settings.nexusops_admin_password,
        )
