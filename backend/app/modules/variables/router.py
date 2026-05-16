from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db_session
from backend.app.modules.variables.repository import VariableRepository
from backend.app.modules.variables.schemas import VariableCreate, VariableRead
from backend.app.modules.variables.service import VariableConflictError, VariableService

router = APIRouter()


async def get_variable_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> VariableService:
    return VariableService(repository=VariableRepository(session))


@router.get("", response_model=list[VariableRead])
async def list_variables(
    service: Annotated[VariableService, Depends(get_variable_service)],
) -> list[VariableRead]:
    return await service.list_variables()


@router.post("", response_model=VariableRead, status_code=status.HTTP_201_CREATED)
async def create_variable(
    payload: VariableCreate,
    service: Annotated[VariableService, Depends(get_variable_service)],
) -> VariableRead:
    try:
        return await service.create_variable(payload)
    except VariableConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
