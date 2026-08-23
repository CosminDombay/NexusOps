from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.router import api_v1_router
from backend.app.core.config import ProductionConfigurationError, settings
from backend.app.core.logging import configure_logging
from backend.app.core.security import InMemoryRateLimitMiddleware, SecurityHeadersMiddleware
from backend.app.db.session import AsyncSessionLocal, get_db_session
from backend.app.modules.auth.repositories.user_repository import UserRepository
from backend.app.modules.auth.services.auth_service import AuthService
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.integrations.repository import IntegrationRepository
from backend.app.modules.integrations.service import IntegrationService
from backend.app.modules.orchestration.reconciliation import reconcile_interrupted_executions
from backend.app.workers.scheduler.service import scheduler_service


def create_app() -> FastAPI:
    configure_logging()
    logger = structlog.get_logger(__name__)
    try:
        settings.validate_startup_configuration()
    except ProductionConfigurationError:
        logger.error("startup.configuration_invalid", environment=settings.environment)
        raise
    for warning in settings.startup_warnings():
        logger.warning("startup.configuration_warning", warning=warning, environment=settings.environment)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        scheduler_enabled = get_db_session not in app.dependency_overrides
        if scheduler_enabled:
            await bootstrap_admin()
            await bootstrap_integrations()
            # Close out work abandoned by the previous process before the
            # scheduler starts queueing new work against the same records.
            await reconcile_interrupted_executions()
            await scheduler_service.start()
        try:
            yield
        finally:
            if scheduler_enabled:
                await scheduler_service.shutdown()

    app = FastAPI(
        title="NexusOps API",
        version="0.1.0",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json" if settings.enable_openapi or not settings.is_production else None,
        docs_url="/docs" if settings.enable_openapi or not settings.is_production else None,
        redoc_url="/redoc" if settings.enable_openapi or not settings.is_production else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(InMemoryRateLimitMiddleware)

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


async def bootstrap_integrations() -> None:
    async with AsyncSessionLocal() as session:
        await IntegrationService(
            IntegrationRepository(session),
            credential_service=CredentialService(repository=CredentialRepository(session)),
        ).bootstrap_default_proxmox_from_env()
