from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db_session
from backend.app.modules.audit.service import audit_service_from_session, source_ip_from_request
from backend.app.modules.auth.models import User
from backend.app.modules.auth.repositories.user_repository import RefreshTokenSessionRepository, UserRepository
from backend.app.modules.auth.schemas.auth import LoginRequest, RefreshRequest, TokenPair, UserCreate, UserPasswordReset, UserRead, UserUpdate
from backend.app.modules.auth.security.dependencies import get_current_user, require_admin
from backend.app.modules.auth.security.jwt import TokenValidationError, decode_token
from backend.app.modules.auth.services.auth_service import (
    AuthenticationError,
    AuthService,
    InactiveUserError,
    RefreshTokenReplayError,
    UserManagementError,
    UserNotFoundError,
)

router = APIRouter()
logger = structlog.get_logger(__name__)


async def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthService:
    return AuthService(
        repository=UserRepository(session),
        refresh_repository=RefreshTokenSessionRepository(session),
    )


@router.post("/login", response_model=TokenPair)
async def login(
    payload: LoginRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenPair:
    try:
        token_pair = await service.login(
            payload,
            user_agent=request.headers.get("user-agent"),
            source_ip=source_ip_from_request(request),
        )
        await audit_service_from_session(session).record(
            event_type="auth.login",
            actor_user_id=token_pair.user.id,
            actor_username=token_pair.user.username,
            target_type="user",
            target_id=token_pair.user.id,
            result="success",
            source_ip=source_ip_from_request(request),
            metadata={"role": token_pair.user.role},
        )
        return token_pair
    except AuthenticationError as exc:
        await audit_service_from_session(session).record(
            event_type="auth.login",
            actor_username=payload.username_or_email,
            target_type="user",
            result="failed",
            source_ip=source_ip_from_request(request),
            error="invalid_credentials",
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except InactiveUserError as exc:
        await audit_service_from_session(session).record(
            event_type="auth.login",
            actor_username=payload.username_or_email,
            target_type="user",
            result="failed",
            source_ip=source_ip_from_request(request),
            error="inactive_user",
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest,
    request: Request,
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
    if int(token_payload["ver"]) != user.token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")

    try:
        refresh_session = await service.validate_refresh_session(
            user=user,
            token_payload=token_payload,
            refresh_token=payload.refresh_token,
        )
        token_pair = await service.refresh(
            user,
            refresh_session=refresh_session,
            user_agent=request.headers.get("user-agent"),
            source_ip=source_ip_from_request(request),
        )
        await audit_service_from_session(session).record(
            event_type="auth.refresh",
            actor=user,
            target_type="user",
            target_id=user.id,
            result="success",
            source_ip=source_ip_from_request(request),
        )
        return token_pair
    except InactiveUserError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except RefreshTokenReplayError as exc:
        await audit_service_from_session(session).record(
            event_type="auth.refresh_replay_detected",
            actor=user,
            target_type="user",
            target_id=user.id,
            result="failed",
            source_ip=source_ip_from_request(request),
            error=str(exc),
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token replay detected") from exc
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    session_id = None
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        try:
            token_payload = decode_token(authorization.split(" ", 1)[1], expected_type="access")
            sid = token_payload.get("sid")
            session_id = UUID(str(sid)) if sid else None
        except (TokenValidationError, ValueError):
            session_id = None
    await service.revoke_current_session(current_user, session_id)
    await audit_service_from_session(session).record(
        event_type="auth.logout",
        actor=current_user,
        target_type="user",
        target_id=current_user.id,
        result="success",
        source_ip=source_ip_from_request(request),
    )
    logger.info("auth.logout", user_id=str(current_user.id), username=current_user.username)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    await service.revoke_user_tokens(current_user)
    await audit_service_from_session(session).record(
        event_type="auth.logout_all",
        actor=current_user,
        target_type="user",
        target_id=current_user.id,
        result="success",
        source_ip=source_ip_from_request(request),
    )


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
