from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.ssh import ParamikoSshAdapter
from backend.app.db.session import get_db_session
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.service import CredentialNotFoundError, CredentialService
from backend.app.modules.identity.repository import (
    IdentityExecutionRepository,
    LinuxGroupRepository,
    LinuxUserRepository,
    PermissionTemplateRepository,
    SSHKeyRepository,
)
from backend.app.modules.identity.schemas import (
    AccessProfileRead,
    GroupDiscoveryRead,
    GroupMembershipRead,
    GroupMembersRequest,
    GroupPresetRead,
    IdentityMutationRead,
    IdentityReplicationRead,
    LinuxGroupCreate,
    LinuxGroupRead,
    LinuxGroupUpdate,
    LinuxUserCreate,
    LinuxUserRead,
    LinuxUserUpdate,
    PermissionApplyRequest,
    PermissionPresetRead,
    PermissionReplicateRequest,
    PermissionTemplateCreate,
    PermissionTemplateRead,
    ReplicationRequest,
    SSHKeyCreate,
    SSHKeyDeployRequest,
    SSHKeyRead,
    UserDiscoveryRead,
    UserGroupMembershipRead,
)
from backend.app.modules.identity.service import (
    IdentityConflictError,
    IdentityNotFoundError,
    IdentityPresetService,
    IdentityReplicationService,
    IdentityValidationError,
    LinuxGroupService,
    LinuxPermissionService,
    LinuxSSHKeyService,
    LinuxUserService,
)
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.jobs.repository import JobRepository
from backend.app.modules.jobs.service import JobService, JobTargetNotFoundError, JobTargetNotManagedError

router = APIRouter()


def _replication_service(session: AsyncSession) -> IdentityReplicationService:
    server_repository = ServerRepository(session)
    return IdentityReplicationService(
        execution_repository=IdentityExecutionRepository(session),
        job_service=JobService(
            job_repository=JobRepository(session),
            server_repository=server_repository,
            ssh_adapter=ParamikoSshAdapter(),
        ),
    )


async def get_user_service(session: Annotated[AsyncSession, Depends(get_db_session)]) -> LinuxUserService:
    return LinuxUserService(
        repository=LinuxUserRepository(session),
        replication_service=_replication_service(session),
        credential_service=CredentialService(repository=CredentialRepository(session)),
    )


async def get_group_service(session: Annotated[AsyncSession, Depends(get_db_session)]) -> LinuxGroupService:
    return LinuxGroupService(
        repository=LinuxGroupRepository(session),
        replication_service=_replication_service(session),
    )


async def get_key_service(session: Annotated[AsyncSession, Depends(get_db_session)]) -> LinuxSSHKeyService:
    return LinuxSSHKeyService(
        repository=SSHKeyRepository(session),
        replication_service=_replication_service(session),
    )


async def get_permission_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LinuxPermissionService:
    return LinuxPermissionService(
        repository=PermissionTemplateRepository(session),
        replication_service=_replication_service(session),
    )


async def get_preset_service() -> IdentityPresetService:
    return IdentityPresetService()


@router.get("/users", response_model=list[LinuxUserRead])
async def list_users(service: Annotated[LinuxUserService, Depends(get_user_service)]) -> list[LinuxUserRead]:
    return await service.list_users()


@router.get("/access-profiles", response_model=list[AccessProfileRead])
async def list_access_profiles(
    service: Annotated[IdentityPresetService, Depends(get_preset_service)],
) -> list[AccessProfileRead]:
    return service.list_access_profiles()


@router.post("/users", response_model=IdentityMutationRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: LinuxUserCreate,
    service: Annotated[LinuxUserService, Depends(get_user_service)],
) -> IdentityMutationRead:
    try:
        return await service.create_user(payload)
    except IdentityConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except CredentialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except IdentityValidationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/users/discover", response_model=UserDiscoveryRead)
async def discover_users(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    target_server_ids: Annotated[list[UUID], Query()],
) -> UserDiscoveryRead:
    if not target_server_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Select at least one target")
    return await _run_identity(lambda: _replication_service(session).discover_users(target_server_ids))


@router.get("/users/{username}/groups", response_model=UserGroupMembershipRead)
async def discover_user_groups(
    username: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    target_server_ids: Annotated[list[UUID], Query()],
) -> UserGroupMembershipRead:
    if not target_server_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Select at least one target")
    return await _run_identity(lambda: _replication_service(session).discover_user_groups(username, target_server_ids))


@router.post("/users/adopt", response_model=IdentityMutationRead, status_code=status.HTTP_201_CREATED)
async def adopt_user(
    payload: LinuxUserCreate,
    service: Annotated[LinuxUserService, Depends(get_user_service)],
) -> IdentityMutationRead:
    try:
        return await service.adopt_user(payload)
    except IdentityConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.put("/users/{user_id}", response_model=IdentityMutationRead)
async def update_user(
    user_id: UUID,
    payload: LinuxUserUpdate,
    service: Annotated[LinuxUserService, Depends(get_user_service)],
) -> IdentityMutationRead:
    try:
        return await service.update_user(user_id, payload)
    except IdentityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CredentialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except IdentityValidationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    service: Annotated[LinuxUserService, Depends(get_user_service)],
    target_server_ids: Annotated[list[UUID] | None, Body()] = None,
    remove_home: Annotated[bool, Query()] = False,
) -> None:
    await _run_identity(lambda: service.delete_user(user_id, target_server_ids, remove_home=remove_home))


@router.post("/users/{user_id}/lock", response_model=IdentityReplicationRead)
async def lock_user(
    user_id: UUID,
    payload: ReplicationRequest,
    service: Annotated[LinuxUserService, Depends(get_user_service)],
) -> IdentityReplicationRead:
    return await _run_identity(lambda: service.lock_user(user_id, payload))


@router.post("/users/{user_id}/unlock", response_model=IdentityReplicationRead)
async def unlock_user(
    user_id: UUID,
    payload: ReplicationRequest,
    service: Annotated[LinuxUserService, Depends(get_user_service)],
) -> IdentityReplicationRead:
    return await _run_identity(lambda: service.unlock_user(user_id, payload))


@router.post("/users/{user_id}/expire-password", response_model=IdentityReplicationRead)
async def expire_user_password(
    user_id: UUID,
    payload: ReplicationRequest,
    service: Annotated[LinuxUserService, Depends(get_user_service)],
) -> IdentityReplicationRead:
    return await _run_identity(lambda: service.expire_password(user_id, payload))


@router.post("/users/{user_id}/disable-shell", response_model=IdentityReplicationRead)
async def disable_user_shell(
    user_id: UUID,
    payload: ReplicationRequest,
    service: Annotated[LinuxUserService, Depends(get_user_service)],
) -> IdentityReplicationRead:
    return await _run_identity(lambda: service.disable_shell(user_id, payload))


@router.post("/users/{user_id}/replicate", response_model=IdentityReplicationRead)
async def replicate_user(
    user_id: UUID,
    payload: ReplicationRequest,
    service: Annotated[LinuxUserService, Depends(get_user_service)],
) -> IdentityReplicationRead:
    return await _run_identity(lambda: service.replicate_user(user_id, payload))


@router.get("/groups", response_model=list[LinuxGroupRead])
async def list_groups(service: Annotated[LinuxGroupService, Depends(get_group_service)]) -> list[LinuxGroupRead]:
    return await service.list_groups()


@router.get("/groups/presets", response_model=list[GroupPresetRead])
async def list_group_presets(
    service: Annotated[IdentityPresetService, Depends(get_preset_service)],
) -> list[GroupPresetRead]:
    return service.list_group_presets()


@router.get("/groups/discover", response_model=GroupDiscoveryRead)
async def discover_groups(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    target_server_ids: Annotated[list[UUID], Query()],
) -> GroupDiscoveryRead:
    if not target_server_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Select at least one target")
    return await _run_identity(lambda: _replication_service(session).discover_groups(target_server_ids))


@router.get("/groups/{group_name}/members/discover", response_model=GroupMembershipRead)
async def discover_group_members(
    group_name: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    target_server_ids: Annotated[list[UUID], Query()],
) -> GroupMembershipRead:
    if not target_server_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Select at least one target")
    return await _run_identity(lambda: _replication_service(session).discover_group_members(group_name, target_server_ids))


@router.post("/groups", response_model=IdentityMutationRead, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: LinuxGroupCreate,
    service: Annotated[LinuxGroupService, Depends(get_group_service)],
) -> IdentityMutationRead:
    try:
        return await service.create_group(payload)
    except IdentityConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/groups/adopt", response_model=IdentityMutationRead, status_code=status.HTTP_201_CREATED)
async def adopt_group(
    payload: LinuxGroupCreate,
    service: Annotated[LinuxGroupService, Depends(get_group_service)],
) -> IdentityMutationRead:
    try:
        return await service.adopt_group(payload)
    except IdentityConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.put("/groups/{group_id}", response_model=IdentityMutationRead)
async def update_group(
    group_id: UUID,
    payload: LinuxGroupUpdate,
    service: Annotated[LinuxGroupService, Depends(get_group_service)],
) -> IdentityMutationRead:
    try:
        return await service.update_group(group_id, payload)
    except IdentityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except IdentityConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: UUID,
    service: Annotated[LinuxGroupService, Depends(get_group_service)],
    target_server_ids: Annotated[list[UUID] | None, Body()] = None,
) -> None:
    try:
        await service.delete_group(group_id, target_server_ids)
    except IdentityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/groups/{group_id}/members", response_model=IdentityReplicationRead)
async def add_group_members(
    group_id: UUID,
    payload: GroupMembersRequest,
    service: Annotated[LinuxGroupService, Depends(get_group_service)],
) -> IdentityReplicationRead:
    return await _run_identity(lambda: service.add_members(group_id, payload))


@router.delete("/groups/{group_id}/members", response_model=IdentityReplicationRead)
async def remove_group_members(
    group_id: UUID,
    payload: GroupMembersRequest,
    service: Annotated[LinuxGroupService, Depends(get_group_service)],
) -> IdentityReplicationRead:
    return await _run_identity(lambda: service.remove_members(group_id, payload))


@router.post("/groups/{group_id}/replicate", response_model=IdentityReplicationRead)
async def replicate_group(
    group_id: UUID,
    payload: ReplicationRequest,
    service: Annotated[LinuxGroupService, Depends(get_group_service)],
) -> IdentityReplicationRead:
    return await _run_identity(lambda: service.replicate_group(group_id, payload))


@router.get("/ssh-keys", response_model=list[SSHKeyRead])
async def list_ssh_keys(service: Annotated[LinuxSSHKeyService, Depends(get_key_service)]) -> list[SSHKeyRead]:
    return await service.list_keys()


@router.post("/ssh-keys", response_model=SSHKeyRead, status_code=status.HTTP_201_CREATED)
async def create_ssh_key(
    payload: SSHKeyCreate,
    service: Annotated[LinuxSSHKeyService, Depends(get_key_service)],
) -> SSHKeyRead:
    return await service.create_key(payload)


@router.post("/ssh-keys/{key_id}/deploy", response_model=IdentityReplicationRead)
async def deploy_ssh_key(
    key_id: UUID,
    payload: SSHKeyDeployRequest,
    service: Annotated[LinuxSSHKeyService, Depends(get_key_service)],
) -> IdentityReplicationRead:
    return await _run_identity(lambda: service.deploy_key(key_id, payload))


@router.post("/ssh-keys/{key_id}/revoke", response_model=IdentityReplicationRead)
async def revoke_ssh_key(
    key_id: UUID,
    payload: SSHKeyDeployRequest,
    service: Annotated[LinuxSSHKeyService, Depends(get_key_service)],
) -> IdentityReplicationRead:
    return await _run_identity(lambda: service.revoke_key(key_id, payload))


@router.get("/permissions", response_model=list[PermissionTemplateRead])
async def list_permissions(
    service: Annotated[LinuxPermissionService, Depends(get_permission_service)],
) -> list[PermissionTemplateRead]:
    return await service.list_templates()


@router.get("/permissions/presets", response_model=list[PermissionPresetRead])
async def list_permission_presets(
    service: Annotated[IdentityPresetService, Depends(get_preset_service)],
) -> list[PermissionPresetRead]:
    return service.list_permission_presets()


@router.post("/permissions", response_model=PermissionTemplateRead, status_code=status.HTTP_201_CREATED)
async def create_permission_template(
    payload: PermissionTemplateCreate,
    service: Annotated[LinuxPermissionService, Depends(get_permission_service)],
) -> PermissionTemplateRead:
    return await service.create_template(payload)


@router.post("/permissions/apply", response_model=IdentityReplicationRead)
async def apply_permissions(
    payload: PermissionApplyRequest,
    service: Annotated[LinuxPermissionService, Depends(get_permission_service)],
) -> IdentityReplicationRead:
    return await _run_identity(lambda: service.apply(payload))


@router.post("/permissions/{template_id}/replicate", response_model=IdentityReplicationRead)
async def replicate_permissions(
    template_id: UUID,
    payload: PermissionReplicateRequest,
    service: Annotated[LinuxPermissionService, Depends(get_permission_service)],
) -> IdentityReplicationRead:
    return await _run_identity(lambda: service.replicate(template_id, payload))


async def _run_identity(operation):
    try:
        return await operation()
    except IdentityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CredentialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (IdentityValidationError, JobTargetNotManagedError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except JobTargetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
