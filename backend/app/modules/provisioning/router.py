from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.proxmox import (
    HttpProxmoxAdapter,
    ProxmoxConfigurationError,
    ProxmoxConnectionError,
)
from backend.app.adapters.ssh import ParamikoSshAdapter
from backend.app.db.session import get_db_session
from backend.app.modules.audit.service import audit_service_from_session, source_ip_from_request
from backend.app.modules.auth.models import User
from backend.app.modules.auth.security.dependencies import require_operator
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.integrations.repository import IntegrationRepository
from backend.app.modules.integrations.service import IntegrationNotFoundError, IntegrationService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.jobs.repository import JobRepository
from backend.app.modules.packages.repository import PackageDefinitionRepository
from backend.app.modules.profiles.repository import InfrastructureProfileRepository
from backend.app.modules.provisioning.repository import (
    ProvisioningBatchRepository,
    ProvisioningBlueprintRepository,
    ProvisioningBootstrapTemplateRepository,
    ProvisioningRequestRepository,
)
from backend.app.modules.provisioning.schemas import (
    ProvisioningBatchCreate,
    ProvisioningBatchRead,
    ProvisioningBlueprintCreate,
    ProvisioningBlueprintRead,
    ProvisioningBlueprintUpdate,
    ProvisioningBootstrapTemplateCreate,
    ProvisioningBootstrapTemplateRead,
    ProvisioningBootstrapTemplateUpdate,
    ProvisioningCleanupRead,
    ProvisioningCreate,
    ProvisioningRead,
    ProxmoxTemplateRead,
)
from backend.app.modules.provisioning.service import (
    ProvisioningBatchNotFoundError,
    ProvisioningBlueprintConflictError,
    ProvisioningBlueprintNotFoundError,
    ProvisioningBootstrapTemplateConflictError,
    ProvisioningBootstrapTemplateNotFoundError,
    ProvisioningNotFoundError,
    ProvisioningService,
)

router = APIRouter()


async def get_provisioning_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProvisioningService:
    credential_service = CredentialService(repository=CredentialRepository(session))
    integration_service = IntegrationService(
        IntegrationRepository(session),
        credential_service=credential_service,
    )
    try:
        proxmox_adapter = await integration_service.get_proxmox_adapter()
    except IntegrationNotFoundError:
        proxmox_adapter = HttpProxmoxAdapter(api_url=" ", token_id="", token_secret="")

    return ProvisioningService(
        repository=ProvisioningRequestRepository(session),
        blueprint_repository=ProvisioningBlueprintRepository(session),
        bootstrap_template_repository=ProvisioningBootstrapTemplateRepository(session),
        batch_repository=ProvisioningBatchRepository(session),
        server_repository=ServerRepository(session),
        job_repository=JobRepository(session),
        package_repository=PackageDefinitionRepository(session),
        profile_repository=InfrastructureProfileRepository(session),
        credential_service=credential_service,
        proxmox_adapter=proxmox_adapter,
        ssh_adapter=ParamikoSshAdapter(),
    )


def _map_provider_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ProxmoxConfigurationError):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    if isinstance(exc, ProxmoxConnectionError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("", response_model=list[ProvisioningRead])
async def list_provisioning_requests(
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
) -> list[ProvisioningRead]:
    return await service.list_requests()


@router.get("/templates", response_model=list[ProxmoxTemplateRead])
async def list_templates(
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
) -> list[ProxmoxTemplateRead]:
    try:
        return await service.list_templates()
    except (ProxmoxConfigurationError, ProxmoxConnectionError) as exc:
        raise _map_provider_error(exc) from exc


@router.get("/blueprints", response_model=list[ProvisioningBlueprintRead])
async def list_blueprints(
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
) -> list[ProvisioningBlueprintRead]:
    return await service.list_blueprints()


@router.get("/batches", response_model=list[ProvisioningBatchRead])
async def list_batches(
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
) -> list[ProvisioningBatchRead]:
    return await service.list_batches()


@router.get("/bootstrap-templates", response_model=list[ProvisioningBootstrapTemplateRead])
async def list_bootstrap_templates(
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
) -> list[ProvisioningBootstrapTemplateRead]:
    return await service.list_bootstrap_templates()


@router.post(
    "/bootstrap-templates",
    response_model=ProvisioningBootstrapTemplateRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_bootstrap_template(
    payload: ProvisioningBootstrapTemplateCreate,
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
) -> ProvisioningBootstrapTemplateRead:
    try:
        return await service.create_bootstrap_template(payload)
    except ProvisioningBootstrapTemplateConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.put("/bootstrap-templates/{template_id}", response_model=ProvisioningBootstrapTemplateRead)
async def update_bootstrap_template(
    template_id: UUID,
    payload: ProvisioningBootstrapTemplateUpdate,
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
) -> ProvisioningBootstrapTemplateRead:
    try:
        return await service.update_bootstrap_template(template_id, payload)
    except ProvisioningBootstrapTemplateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProvisioningBootstrapTemplateConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/bootstrap-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bootstrap_template(
    template_id: UUID,
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
) -> None:
    try:
        await service.delete_bootstrap_template(template_id)
    except ProvisioningBootstrapTemplateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/batches", response_model=ProvisioningBatchRead, status_code=status.HTTP_201_CREATED)
async def provision_batch(
    payload: ProvisioningBatchCreate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(require_operator)],
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
) -> ProvisioningBatchRead:
    try:
        batch = await service.provision_batch(payload)
        await audit_service_from_session(session).record(
            event_type="provisioning.batch_created",
            actor=current_user,
            target_type="provisioning_batch",
            target_id=batch.id,
            result="success",
            source_ip=source_ip_from_request(request),
            metadata={"blueprint_id": str(payload.blueprint_id), "count": payload.count},
        )
        return batch
    except ProvisioningBlueprintNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ProxmoxConfigurationError, ProxmoxConnectionError) as exc:
        raise _map_provider_error(exc) from exc


@router.get("/batches/{batch_id}", response_model=ProvisioningBatchRead)
async def get_batch(
    batch_id: UUID,
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
) -> ProvisioningBatchRead:
    try:
        return await service.get_batch(batch_id)
    except ProvisioningBatchNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/sanitize-stale",
    response_model=ProvisioningCleanupRead,
    dependencies=[Depends(require_operator)],
)
async def sanitize_stale_provisioning_requests(
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
    dry_run: bool = False,
) -> ProvisioningCleanupRead:
    return await service.sanitize_stale_requests(dry_run=dry_run)


@router.post("/blueprints", response_model=ProvisioningBlueprintRead, status_code=status.HTTP_201_CREATED)
async def create_blueprint(
    payload: ProvisioningBlueprintCreate,
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
) -> ProvisioningBlueprintRead:
    try:
        return await service.create_blueprint(payload)
    except ProvisioningBlueprintConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.put("/blueprints/{blueprint_id}", response_model=ProvisioningBlueprintRead)
async def update_blueprint(
    blueprint_id: UUID,
    payload: ProvisioningBlueprintUpdate,
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
) -> ProvisioningBlueprintRead:
    try:
        return await service.update_blueprint(blueprint_id, payload)
    except ProvisioningBlueprintNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProvisioningBlueprintConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/blueprints/{blueprint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_blueprint(
    blueprint_id: UUID,
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
) -> None:
    try:
        await service.delete_blueprint(blueprint_id)
    except ProvisioningBlueprintNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{request_id}", response_model=ProvisioningRead)
async def get_provisioning_request(
    request_id: UUID,
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
) -> ProvisioningRead:
    try:
        return await service.get_request(request_id)
    except ProvisioningNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provisioning_request(
    request_id: UUID,
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
) -> None:
    try:
        await service.delete_request(request_id)
    except ProvisioningNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("", response_model=ProvisioningRead, status_code=status.HTTP_201_CREATED)
async def provision_vm(
    payload: ProvisioningCreate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(require_operator)],
    service: Annotated[ProvisioningService, Depends(get_provisioning_service)],
) -> ProvisioningRead:
    try:
        provisioning = await service.provision(payload)
        await audit_service_from_session(session).record(
            event_type="provisioning.request_created",
            actor=current_user,
            target_type="provisioning_request",
            target_id=provisioning.id,
            result="success" if provisioning.status.value != "failed" else "failed",
            source_ip=source_ip_from_request(request),
            metadata={
                "vm_name": provisioning.vm_name,
                "new_vm_id": provisioning.new_vm_id,
                "provisioning_type": provisioning.provisioning_type,
                "server_id": str(provisioning.server_id) if provisioning.server_id else None,
            },
            error=provisioning.error_message,
        )
        return provisioning
    except (ProxmoxConfigurationError, ProxmoxConnectionError) as exc:
        raise _map_provider_error(exc) from exc
