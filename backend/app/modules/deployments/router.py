from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.ssh import ParamikoSshAdapter
from backend.app.db.session import AsyncSessionLocal, get_db_session
from backend.app.modules.audit.repository import AuditEventRepository
from backend.app.modules.audit.service import AuditService
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.deployments.repository import (
    DeploymentExecutionRepository,
    DeploymentRepository,
    DeploymentRevisionRepository,
    DeploymentTargetRepository,
    DeploymentTargetExecutionRepository,
)
from backend.app.modules.deployments.schemas import (
    DeploymentCreate,
    DeploymentDryRunRead,
    DeploymentExportRead,
    DeploymentImportRead,
    DeploymentImportRequest,
    DeploymentLogsRead,
    DeploymentOperationRead,
    DeploymentRead,
    DeploymentStatusRead,
    DeploymentUpdate,
)
from backend.app.modules.deployments.service import (
    DeploymentNotFoundError,
    DeploymentImportError,
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
        execution_repository=DeploymentExecutionRepository(session),
        target_execution_repository=DeploymentTargetExecutionRepository(session),
        server_repository=server_repository,
        job_service=JobService(
            job_repository=JobRepository(session),
            server_repository=server_repository,
            ssh_adapter=ParamikoSshAdapter(),
            credential_service=CredentialService(repository=CredentialRepository(session)),
            audit_service=AuditService(AuditEventRepository(session)),
            session_factory=AsyncSessionLocal,
        ),
        credential_service=CredentialService(repository=CredentialRepository(session)),
    )


@router.get("", response_model=list[DeploymentRead])
async def list_deployments(
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
    server_id: UUID | None = None,
) -> list[DeploymentRead]:
    return await service.list_deployments(server_id=server_id)


@router.post("", response_model=DeploymentRead, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    payload: DeploymentCreate,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> DeploymentRead:
    try:
        return await service.create_deployment(payload)
    except DeploymentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except JobTargetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobTargetNotManagedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/import", response_model=DeploymentImportRead, status_code=status.HTTP_201_CREATED)
async def import_deployment(
    payload: DeploymentImportRequest,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> DeploymentImportRead:
    try:
        return await service.import_deployment(payload)
    except DeploymentImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DeploymentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/validate", response_model=DeploymentDryRunRead)
async def validate_deployment_payload(
    payload: DeploymentCreate,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
    operation: str = "deploy",
) -> DeploymentDryRunRead:
    return await _run(lambda: service.validate_payload(payload, operation))


@router.post("/{deployment_id}/deploy", response_model=DeploymentOperationRead)
async def deploy(
    deployment_id: UUID,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> DeploymentOperationRead:
    return await _run(lambda: service.deploy(deployment_id))


@router.get("/{deployment_id}/dry-run", response_model=DeploymentDryRunRead)
async def dry_run(
    deployment_id: UUID,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
    operation: str = "deploy",
) -> DeploymentDryRunRead:
    return await _run(lambda: service.dry_run(deployment_id, operation))


@router.get("/{deployment_id}/export", response_model=DeploymentExportRead)
async def export_deployment(
    deployment_id: UUID,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
    format: str = "json",
) -> DeploymentExportRead:
    if format not in {"json", "yaml"}:
        raise HTTPException(status_code=422, detail="Export format must be json or yaml")
    return await _run(lambda: service.export_deployment(deployment_id, format))


@router.delete("/{deployment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment(
    deployment_id: UUID,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> None:
    await _run(lambda: service.delete_deployment(deployment_id))


@router.put("/{deployment_id}", response_model=DeploymentRead)
async def update_deployment(
    deployment_id: UUID,
    payload: DeploymentUpdate,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> DeploymentRead:
    return await _run(lambda: service.update_deployment(deployment_id, payload))


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


@router.post("/{deployment_id}/mark-planned", response_model=DeploymentRead)
async def mark_planned(
    deployment_id: UUID,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> DeploymentRead:
    return await _run(lambda: service.mark_planned(deployment_id))


@router.get("/{deployment_id}/status", response_model=DeploymentStatusRead)
async def get_status(
    deployment_id: UUID,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> DeploymentStatusRead:
    return await _run(lambda: service.status(deployment_id))


@router.post("/{deployment_id}/refresh-runtime", response_model=DeploymentRead)
async def refresh_runtime(
    deployment_id: UUID,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> DeploymentRead:
    return await _run(lambda: service.refresh_runtime(deployment_id))


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
