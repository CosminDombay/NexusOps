from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog

from backend.app.adapters.ssh import ParamikoSshAdapter
from backend.app.core.config import settings
from backend.app.db.session import AsyncSessionLocal
from backend.app.modules.audit.repository import AuditEventRepository
from backend.app.modules.audit.service import AuditService
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.deployments.models import DeploymentStatus
from backend.app.modules.deployments.repository import (
    DeploymentExecutionRepository,
    DeploymentRepository,
    DeploymentRevisionRepository,
    DeploymentTargetExecutionRepository,
    DeploymentTargetRepository,
)
from backend.app.modules.deployments.service import DockerComposeDeploymentService
from backend.app.modules.inventory.health import InventoryHealthService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.jobs.repository import JobRepository
from backend.app.modules.jobs.service import JobService
from backend.app.workers.queue.service import task_queue

logger = structlog.get_logger(__name__)

_refresh_lock = asyncio.Lock()
_last_started_at: datetime | None = None


def submit_runtime_refresh(*, reason: str, force: bool = False) -> bool:
    if not settings.runtime_refresh_enabled:
        logger.info("runtime_refresh_submit_skipped", reason=reason, disabled=True)
        return False
    task_queue.submit(
        run_runtime_refresh(reason=reason, force=force),
        name=f"runtime-refresh:{reason}",
        owner="runtime",
        execution_origin="runtime_refresh",
    )
    return True


async def run_runtime_refresh(*, reason: str, force: bool = False) -> None:
    global _last_started_at
    now = datetime.now(UTC)
    if _refresh_lock.locked():
        logger.info("runtime_refresh_skipped", reason=reason, skip_reason="already_running")
        return
    if (
        not force
        and _last_started_at is not None
        and (now - _last_started_at).total_seconds() < settings.runtime_refresh_min_interval_seconds
    ):
        logger.info("runtime_refresh_skipped", reason=reason, skip_reason="recently_refreshed")
        return

    async with _refresh_lock:
        _last_started_at = datetime.now(UTC)
        started_at = _last_started_at
        logger.info("runtime_refresh_started", reason=reason)
        try:
            await asyncio.wait_for(
                _refresh_runtime_state(reason=reason),
                timeout=settings.runtime_refresh_timeout_seconds,
            )
        except TimeoutError:
            logger.warning(
                "runtime_refresh_timeout",
                reason=reason,
                timeout_seconds=settings.runtime_refresh_timeout_seconds,
            )
        except Exception as exc:
            logger.warning("runtime_refresh_failed", reason=reason, error=str(exc))
        else:
            logger.info(
                "runtime_refresh_completed",
                reason=reason,
                duration_seconds=round((datetime.now(UTC) - started_at).total_seconds(), 2),
            )


async def _refresh_runtime_state(*, reason: str) -> None:
    async with AsyncSessionLocal() as session:
        servers = await ServerRepository(session).list()

    semaphore = asyncio.Semaphore(settings.runtime_refresh_concurrency)

    async def check_server(server_id) -> object | None:
        async with semaphore:
            async with AsyncSessionLocal() as session:
                try:
                    return await InventoryHealthService(ServerRepository(session)).check_server(server_id)
                except Exception as exc:
                    logger.warning(
                        "runtime_refresh_inventory_node_failed",
                        reason=reason,
                        server_id=str(server_id),
                        error=str(exc),
                    )
                    return None

    health_results = [
        result
        for result in await asyncio.gather(*(check_server(server.id) for server in servers))
        if result is not None
    ]
    logger.info(
        "runtime_refresh_inventory_completed",
        reason=reason,
        checked=len(health_results),
        unreachable=sum(1 for item in health_results if getattr(item, "status", None) == "unreachable"),
    )

    async with AsyncSessionLocal() as session:
        service = _deployment_service(session)
        deployments = await service.repository.list()
        refreshed = 0
        failed = 0
        for deployment in deployments:
            if deployment.status == DeploymentStatus.DRAFT:
                continue
            targets = await service.target_repository.list_for_deployment(deployment.id)
            if not targets:
                continue
            try:
                await service.runtime_reconciler.reconcile(deployment, targets)
                refreshed += 1
            except Exception as exc:
                failed += 1
                logger.warning(
                    "runtime_refresh_deployment_failed",
                    reason=reason,
                    deployment_id=str(deployment.id),
                    error=str(exc),
                )
        logger.info(
            "runtime_refresh_deployments_completed",
            reason=reason,
            refreshed=refreshed,
            failed=failed,
        )


def _deployment_service(session) -> DockerComposeDeploymentService:
    server_repository = ServerRepository(session)
    credential_service = CredentialService(repository=CredentialRepository(session))
    return DockerComposeDeploymentService(
        repository=DeploymentRepository(session),
        target_repository=DeploymentTargetRepository(session),
        revision_repository=DeploymentRevisionRepository(session),
        execution_repository=DeploymentExecutionRepository(session),
        target_execution_repository=DeploymentTargetExecutionRepository(session),
        server_repository=server_repository,
        job_service=JobService(
            job_repository=JobRepository(session),
            server_repository=server_repository,
            ssh_adapter=ParamikoSshAdapter(),
            credential_service=credential_service,
            audit_service=AuditService(AuditEventRepository(session)),
            session_factory=AsyncSessionLocal,
        ),
        credential_service=credential_service,
    )
