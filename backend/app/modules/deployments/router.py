from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.ssh import ParamikoSshAdapter
from backend.app.db.session import get_db_session
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.deployments.repository import (
    DeploymentRepository,
    DeploymentRevisionRepository,
    DeploymentTargetRepository,
)
from backend.app.modules.deployments.schemas import (
    DeploymentCreate,
    DeploymentLogsRead,
    DeploymentOperationRead,
    DeploymentRead,
    DeploymentStatusRead,
)
from backend.app.modules.deployments.service import (
    DeploymentNotFoundError,
    DeploymentValidationError,
    DockerComposeDeploymentService,
)
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.jobs.repository import JobRepository
from backend.app.modules.jobs.service import JobService, JobTargetNotFoundError, JobTargetNotManagedError

router = APIRouter()


async def get_deployment_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DockerComposeDeploymentService:
    server_repository = ServerRepository(session)
    return DockerComposeDeploymentService(
        repository=DeploymentRepository(session),
        target_repository=DeploymentTargetRepository(session),
        revision_repository=DeploymentRevisionRepository(session),
        server_repository=server_repository,
        job_service=JobService(
            job_repository=JobRepository(session),
            server_repository=server_repository,
            ssh_adapter=ParamikoSshAdapter(),
            credential_service=CredentialService(repository=CredentialRepository(session)),
        ),
        credential_service=CredentialService(repository=CredentialRepository(session)),
    )


@router.get("", response_model=list[DeploymentRead])
async def list_deployments(
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> list[DeploymentRead]:
    return await service.list_deployments()


@router.post("", response_model=DeploymentRead, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    payload: DeploymentCreate,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> DeploymentRead:
    try:
        return await service.create_deployment(payload)
    except JobTargetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobTargetNotManagedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{deployment_id}/deploy", response_model=DeploymentOperationRead)
async def deploy(
    deployment_id: UUID,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> DeploymentOperationRead:
    return await _run(lambda: service.deploy(deployment_id))


@router.post("/{deployment_id}/redeploy", response_model=DeploymentOperationRead)
async def redeploy(
    deployment_id: UUID,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> DeploymentOperationRead:
    return await _run(lambda: service.redeploy(deployment_id))


@router.post("/{deployment_id}/restart", response_model=DeploymentOperationRead)
async def restart(
    deployment_id: UUID,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> DeploymentOperationRead:
    return await _run(lambda: service.restart(deployment_id))


@router.post("/{deployment_id}/stop", response_model=DeploymentOperationRead)
async def stop(
    deployment_id: UUID,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> DeploymentOperationRead:
    return await _run(lambda: service.stop(deployment_id))


@router.get("/{deployment_id}/status", response_model=DeploymentStatusRead)
async def get_status(
    deployment_id: UUID,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> DeploymentStatusRead:
    return await _run(lambda: service.status(deployment_id))


@router.get("/{deployment_id}/logs", response_model=DeploymentLogsRead)
async def get_logs(
    deployment_id: UUID,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> DeploymentLogsRead:
    return await _run(lambda: service.logs(deployment_id))


async def _run(operation):
    try:
        return await operation()
    except DeploymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (DeploymentValidationError, JobTargetNotManagedError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except JobTargetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
