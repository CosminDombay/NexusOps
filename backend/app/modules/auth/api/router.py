from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db_session
from backend.app.modules.auth.models import User
from backend.app.modules.auth.repositories.user_repository import UserRepository
from backend.app.modules.auth.schemas.auth import LoginRequest, RefreshRequest, TokenPair, UserCreate, UserPasswordReset, UserRead, UserUpdate
from backend.app.modules.auth.security.dependencies import get_current_user, require_admin
from backend.app.modules.auth.security.jwt import TokenValidationError, decode_token
from backend.app.modules.auth.services.auth_service import (
    AuthenticationError,
    AuthService,
    InactiveUserError,
    UserManagementError,
    UserNotFoundError,
)

router = APIRouter()
logger = structlog.get_logger(__name__)


async def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthService:
    return AuthService(repository=UserRepository(session))


@router.post("/login", response_model=TokenPair)
async def login(
    payload: LoginRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenPair:
    try:
        return await service.login(payload)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except InactiveUserError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenPair:
    try:
        token_payload = decode_token(payload.refresh_token, expected_type="refresh")
    except TokenValidationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user = await UserRepository(session).get_by_id(UUID(str(token_payload["sub"])))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")

    try:
        return await service.refresh(user)
    except InactiveUserError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: Annotated[User, Depends(get_current_user)]) -> None:
    logger.info("auth.logout", user_id=str(current_user.id), username=current_user.username)


@router.get("/me", response_model=UserRead)
async def me(current_user: Annotated[User, Depends(get_current_user)]) -> UserRead:
    return UserRead.model_validate(current_user)


@router.get("/users", response_model=list[UserRead], dependencies=[Depends(require_admin)])
async def list_users(service: Annotated[AuthService, Depends(get_auth_service)]) -> list[UserRead]:
    return await service.list_users()


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
async def create_user(
    payload: UserCreate,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserRead:
    try:
        return await service.create_user(payload)
    except UserManagementError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.put("/users/{user_id}", response_model=UserRead, dependencies=[Depends(require_admin)])
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserRead:
    try:
        return await service.update_user(user_id, payload)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UserManagementError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/users/{user_id}/reset-password", response_model=UserRead, dependencies=[Depends(require_admin)])
async def reset_user_password(
    user_id: UUID,
    payload: UserPasswordReset,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserRead:
    try:
        return await service.reset_user_password(user_id, payload)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
