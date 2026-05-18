import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db_session
from backend.app.modules.auth.models import User
from backend.app.modules.auth.repositories.user_repository import UserRepository
from backend.app.modules.auth.security.dependencies import get_current_user
from backend.app.modules.auth.security.jwt import TokenValidationError, decode_token
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.remote_access.audit import audit_remote_access_event
from backend.app.modules.remote_access.schemas import (
    RemoteDirectoryListing,
    RemoteFileRead,
    RemoteFileWriteRequest,
    RemoteFileWriteResponse,
)
from backend.app.modules.remote_access.service import (
    RemoteAccessDeniedError,
    RemoteAccessService,
    RemoteAccessTargetError,
    RemoteFileConflictError,
    RemotePathError,
    RemoteSshError,
)

router = APIRouter()


async def get_remote_access_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RemoteAccessService:
    return RemoteAccessService(
        server_repository=ServerRepository(session),
        credential_service=CredentialService(repository=CredentialRepository(session)),
    )


def _map_error(exc: Exception) -> HTTPException:
    if isinstance(exc, RemoteAccessDeniedError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, RemoteAccessTargetError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, RemoteFileConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, RemotePathError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, RemoteSshError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Remote access failed")


@router.websocket("/hosts/{server_id}/shell")
async def shell_websocket(
    websocket: WebSocket,
    server_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    token: Annotated[str | None, Query()] = None,
) -> None:
    user = await _authenticate_websocket(token, session)
    service = RemoteAccessService(
        server_repository=ServerRepository(session),
        credential_service=CredentialService(repository=CredentialRepository(session)),
    )
    await websocket.accept()
    shell = None
    try:
        shell = await service.open_shell(server_id, user)
        audit_remote_access_event("remote_shell_opened", server_id=server_id, user=user)
        await asyncio.gather(
            _websocket_to_shell(websocket, shell.channel),
            _shell_to_websocket(websocket, shell.channel),
        )
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        audit_remote_access_event(
            "remote_shell_failed",
            server_id=server_id,
            user=user,
            outcome="failed",
            reason=exc.__class__.__name__,
        )
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=str(exc))
    finally:
        if shell is not None:
            await asyncio.to_thread(shell.close)
        audit_remote_access_event("remote_shell_closed", server_id=server_id, user=user)


async def _authenticate_websocket(token: str | None, session: AsyncSession) -> User:
    if not token:
        raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)
    try:
        payload = decode_token(token, expected_type="access")
    except TokenValidationError as exc:
        raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION) from exc
    user = await UserRepository(session).get_by_id(UUID(str(payload["sub"])))
    if user is None or not user.is_active:
        raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)
    return user


async def _websocket_to_shell(websocket: WebSocket, channel) -> None:
    while True:
        data = await websocket.receive_text()
        await asyncio.to_thread(channel.send, data)


async def _shell_to_websocket(websocket: WebSocket, channel) -> None:
    while not channel.closed:
        if channel.recv_ready():
            data = await asyncio.to_thread(channel.recv, 4096)
            if not data:
                break
            await websocket.send_text(data.decode("utf-8", errors="replace"))
        else:
            await asyncio.sleep(0.03)


@router.get("/hosts/{server_id}/files", response_model=RemoteDirectoryListing)
async def list_files(
    server_id: UUID,
    service: Annotated[RemoteAccessService, Depends(get_remote_access_service)],
    user: Annotated[User, Depends(get_current_user)],
    path: str = "/",
) -> RemoteDirectoryListing:
    try:
        result = await service.list_files(server_id, path, user)
        audit_remote_access_event("remote_file_listed", server_id=server_id, user=user, path=result.path)
        return result
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/hosts/{server_id}/files/read", response_model=RemoteFileRead)
async def read_file(
    server_id: UUID,
    service: Annotated[RemoteAccessService, Depends(get_remote_access_service)],
    user: Annotated[User, Depends(get_current_user)],
    path: str,
) -> RemoteFileRead:
    try:
        result = await service.read_file(server_id, path, user)
        audit_remote_access_event("remote_file_read", server_id=server_id, user=user, path=result.path)
        return result
    except Exception as exc:
        raise _map_error(exc) from exc


@router.put("/hosts/{server_id}/files/write", response_model=RemoteFileWriteResponse)
async def write_file(
    server_id: UUID,
    payload: RemoteFileWriteRequest,
    service: Annotated[RemoteAccessService, Depends(get_remote_access_service)],
    user: Annotated[User, Depends(get_current_user)],
) -> RemoteFileWriteResponse:
    audit_remote_access_event("remote_file_write_attempted", server_id=server_id, user=user, path=payload.path)
    try:
        result = await service.write_file(
            server_id,
            payload.path,
            payload.content,
            payload.expected_hash,
            user,
        )
        audit_remote_access_event("remote_file_write_succeeded", server_id=server_id, user=user, path=result.path)
        return result
    except Exception as exc:
        audit_remote_access_event(
            "remote_file_write_failed",
            server_id=server_id,
            user=user,
            path=payload.path,
            outcome="failed",
            reason=exc.__class__.__name__,
        )
        raise _map_error(exc) from exc
