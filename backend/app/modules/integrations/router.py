from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db_session
from backend.app.modules.integrations.repository import IntegrationRepository
from backend.app.modules.integrations.schemas import (
    IntegrationCreate,
    IntegrationRead,
    IntegrationTestRead,
    IntegrationUpdate,
)
from backend.app.modules.integrations.service import IntegrationNotFoundError, IntegrationService

router = APIRouter()


async def get_integration_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> IntegrationService:
    return IntegrationService(IntegrationRepository(session))


@router.get("", response_model=list[IntegrationRead])
async def list_integrations(
    service: Annotated[IntegrationService, Depends(get_integration_service)],
) -> list[IntegrationRead]:
    return await service.list_integrations()


@router.post("", response_model=IntegrationRead, status_code=status.HTTP_201_CREATED)
async def create_integration(
    payload: IntegrationCreate,
    service: Annotated[IntegrationService, Depends(get_integration_service)],
) -> IntegrationRead:
    return await service.create_integration(payload)


@router.put("/{integration_id}", response_model=IntegrationRead)
async def update_integration(
    integration_id: UUID,
    payload: IntegrationUpdate,
    service: Annotated[IntegrationService, Depends(get_integration_service)],
) -> IntegrationRead:
    try:
        return await service.update_integration(integration_id, payload)
    except IntegrationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{integration_id}/test", response_model=IntegrationTestRead)
async def test_integration(
    integration_id: UUID,
    service: Annotated[IntegrationService, Depends(get_integration_service)],
) -> IntegrationTestRead:
    try:
        return await service.test_integration(integration_id)
    except IntegrationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
