from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db_session
from backend.app.modules.auth.models import User
from backend.app.modules.auth.repositories.user_repository import UserRepository
from backend.app.modules.auth.schemas.auth import LoginRequest, RefreshRequest, TokenPair, UserRead
from backend.app.modules.auth.security.dependencies import get_current_user
from backend.app.modules.auth.security.jwt import TokenValidationError, decode_token
from backend.app.modules.auth.services.auth_service import (
    AuthenticationError,
    AuthService,
    InactiveUserError,
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
