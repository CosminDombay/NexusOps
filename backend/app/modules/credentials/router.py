from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db_session
from backend.app.modules.credentials.encryption_service import EncryptionConfigurationError
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.schemas import CredentialCreate, CredentialRead, CredentialUpdate
from backend.app.modules.credentials.service import (
    CredentialConflictError,
    CredentialNotFoundError,
    CredentialService,
)

router = APIRouter()


async def get_credential_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CredentialService:
    return CredentialService(repository=CredentialRepository(session))


@router.get("", response_model=list[CredentialRead])
async def list_credentials(
    service: Annotated[CredentialService, Depends(get_credential_service)],
) -> list[CredentialRead]:
    return await service.list_credentials()


@router.post("", response_model=CredentialRead, status_code=status.HTTP_201_CREATED)
async def create_credential(
    payload: CredentialCreate,
    service: Annotated[CredentialService, Depends(get_credential_service)],
) -> CredentialRead:
    try:
        return await service.create_credential(payload)
    except CredentialConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except EncryptionConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.put("/{credential_id}", response_model=CredentialRead)
async def update_credential(
    credential_id: UUID,
    payload: CredentialUpdate,
    service: Annotated[CredentialService, Depends(get_credential_service)],
) -> CredentialRead:
    try:
        return await service.update_credential(credential_id, payload)
    except CredentialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CredentialConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except EncryptionConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: UUID,
    service: Annotated[CredentialService, Depends(get_credential_service)],
) -> None:
    try:
        await service.delete_credential(credential_id)
    except CredentialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
