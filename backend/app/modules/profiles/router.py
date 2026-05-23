from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.ssh import ParamikoSshAdapter
from backend.app.db.session import get_db_session
from backend.app.modules.audit.repository import AuditEventRepository
from backend.app.modules.audit.service import AuditService
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.service import CredentialNotFoundError, CredentialService
from backend.app.modules.deployments.repository import (
    DeploymentRepository,
    DeploymentRevisionRepository,
    DeploymentTargetRepository,
)
from backend.app.modules.deployments.service import DeploymentNotFoundError, DeploymentValidationError, DockerComposeDeploymentService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.jobs.repository import CustomOperationalActionRepository, JobRepository
from backend.app.modules.jobs.service import JobService, JobTargetNotFoundError, JobTargetNotManagedError
from backend.app.modules.packages.repository import PackageDefinitionRepository
from backend.app.modules.profiles.repository import InfrastructureProfileRepository
from backend.app.modules.profiles.schemas import (
    InfrastructureProfileCreate,
    InfrastructureProfileRead,
    InfrastructureProfileUpdate,
    ProfileCloneRequest,
    ProfileApplyRead,
    ProfileBulkApplyRead,
    ProfileBulkApplyRequest,
    ProfileApplyRequest,
)
from backend.app.common.variables import VariableResolutionError
from backend.app.modules.profiles.service import (
    BuiltinProfileError,
    ProfileConflictError,
    ProfileNotFoundError,
    ProfileService,
    ProfileStepResolutionError,
)

router = APIRouter()


async def get_profile_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProfileService:
    server_repository = ServerRepository(session)
    credential_service = CredentialService(repository=CredentialRepository(session))
    job_service = JobService(
        job_repository=JobRepository(session),
        server_repository=server_repository,
        ssh_adapter=ParamikoSshAdapter(),
        action_repository=CustomOperationalActionRepository(session),
        credential_service=credential_service,
        audit_service=AuditService(AuditEventRepository(session)),
    )
    return ProfileService(
        job_service=job_service,
        repository=InfrastructureProfileRepository(session),
        package_repository=PackageDefinitionRepository(session),
        deployment_service=DockerComposeDeploymentService(
            repository=DeploymentRepository(session),
            target_repository=DeploymentTargetRepository(session),
            revision_repository=DeploymentRevisionRepository(session),
            server_repository=server_repository,
            job_service=job_service,
            credential_service=credential_service,
        ),
    )


@router.get("", response_model=list[InfrastructureProfileRead])
async def list_profiles(
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> list[InfrastructureProfileRead]:
    return await service.list_profiles()


@router.post("/apply/bulk", response_model=ProfileBulkApplyRead, status_code=status.HTTP_201_CREATED)
async def apply_profile_bulk(
    payload: ProfileBulkApplyRequest,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileBulkApplyRead:
    return await service.apply_profile_bulk(payload)


@router.post("", response_model=InfrastructureProfileRead, status_code=status.HTTP_201_CREATED)
async def create_profile(
    payload: InfrastructureProfileCreate,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> InfrastructureProfileRead:
    try:
        return await service.create_profile(payload)
    except ProfileConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/{profile_id}", response_model=InfrastructureProfileRead)
async def get_profile(
    profile_id: str,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> InfrastructureProfileRead:
    try:
        return await service.get_profile(profile_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/{profile_id}", response_model=InfrastructureProfileRead)
async def update_profile(
    profile_id: str,
    payload: InfrastructureProfileUpdate,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> InfrastructureProfileRead:
    try:
        return await service.update_profile(profile_id, payload)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except BuiltinProfileError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{profile_id}/clone", response_model=InfrastructureProfileRead, status_code=status.HTTP_201_CREATED)
async def clone_profile(
    profile_id: str,
    payload: ProfileCloneRequest,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> InfrastructureProfileRead:
    try:
        return await service.clone_profile(profile_id, payload)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProfileConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{profile_id}/reset", response_model=InfrastructureProfileRead)
async def reset_profile(
    profile_id: str,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> InfrastructureProfileRead:
    try:
        return await service.reset_profile(profile_id)
    except (ProfileNotFoundError, BuiltinProfileError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    profile_id: str,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> None:
    try:
        await service.delete_profile(profile_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except BuiltinProfileError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{profile_id}/apply", response_model=ProfileApplyRead, status_code=status.HTTP_201_CREATED)
async def apply_profile(
    profile_id: str,
    payload: ProfileApplyRequest,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileApplyRead:
    try:
        return await service.apply_profile(profile_id, payload)
    except (ProfileNotFoundError, JobTargetNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobTargetNotManagedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (ProfileStepResolutionError, DeploymentValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DeploymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except VariableResolutionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except CredentialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
