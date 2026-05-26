import asyncio
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db_session
from backend.app.modules.audit.service import audit_service_from_session, source_ip_from_request
from backend.app.modules.auth.models import User, UserRole
from backend.app.core.config import settings
from backend.app.modules.auth.models import RemoteAccessToken
from backend.app.modules.auth.repositories.user_repository import RemoteAccessTokenRepository, UserRepository
from backend.app.modules.auth.security.dependencies import ROLE_ORDER, require_operator
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


class RemoteAccessTokenRead(BaseModel):
    token: str
    expires_at: datetime


class TrustedHostKeyRequest(BaseModel):
    fingerprint: str


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
    user = await _authenticate_websocket(token, session, server_id=server_id, operation="shell")
    service = RemoteAccessService(
        server_repository=ServerRepository(session),
        credential_service=CredentialService(repository=CredentialRepository(session)),
    )
    await websocket.accept()
    shell = None
    try:
        shell = await service.open_shell(server_id, user)
        audit_remote_access_event("remote_shell_opened", server_id=server_id, user=user)
        await audit_service_from_session(session).record(
            event_type="remote_access.shell_opened",
            actor=user,
            target_type="server",
            target_id=server_id,
            result="success",
            source_ip=websocket.client.host if websocket.client else None,
        )
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
        await audit_service_from_session(session).record(
            event_type="remote_access.shell_failed",
            actor=user,
            target_type="server",
            target_id=server_id,
            result="failed",
            source_ip=websocket.client.host if websocket.client else None,
            error=exc.__class__.__name__,
        )
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=str(exc))
    finally:
        if shell is not None:
            await asyncio.to_thread(shell.close)
        audit_remote_access_event("remote_shell_closed", server_id=server_id, user=user)
        await audit_service_from_session(session).record(
            event_type="remote_access.shell_closed",
            actor=user,
            target_type="server",
            target_id=server_id,
            result="success",
            source_ip=websocket.client.host if websocket.client else None,
        )


@router.post("/hosts/{server_id}/shell-token", response_model=RemoteAccessTokenRead)
async def create_shell_token(
    server_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(require_operator)],
) -> RemoteAccessTokenRead:
    token = token_urlsafe(32)
    token_id = token_urlsafe(16)
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=settings.remote_access_token_expire_seconds)
    access_payload = _access_payload_from_request(request)
    session_id = None
    if access_payload and access_payload.get("sid"):
        try:
            session_id = UUID(str(access_payload["sid"]))
        except ValueError:
            session_id = None
    await RemoteAccessTokenRepository(session).create(
        RemoteAccessToken(
            token_id=token_id,
            token_hash=_hash_remote_token(token),
            user_id=user.id,
            server_id=server_id,
            session_id=session_id,
            operation="shell",
            role=user.role.value,
            issued_at=now,
            expires_at=expires_at,
            source_ip=source_ip_from_request(request),
        )
    )
    await session.commit()
    await audit_service_from_session(session).record(
        event_type="remote_access.shell_token_issued",
        actor=user,
        target_type="server",
        target_id=server_id,
        result="success",
        source_ip=source_ip_from_request(request),
        metadata={"operation": "shell", "expires_at": expires_at.isoformat()},
    )
    return RemoteAccessTokenRead(token=f"{token_id}.{token}", expires_at=expires_at)


@router.post("/hosts/{server_id}/trusted-host-key")
async def approve_trusted_host_key(
    server_id: UUID,
    payload: TrustedHostKeyRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(require_operator)],
) -> dict[str, str]:
    server = await ServerRepository(session).get_by_id(server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory server not found")
    server.trusted_ssh_host_key_sha256 = payload.fingerprint.strip()
    server.trusted_ssh_host_key_accepted_at = datetime.now(UTC)
    await session.commit()
    await audit_service_from_session(session).record(
        event_type="remote_access.host_key_approved",
        actor=user,
        target_type="server",
        target_id=server_id,
        result="success",
        source_ip=source_ip_from_request(request),
        metadata={"fingerprint": server.trusted_ssh_host_key_sha256},
    )
    return {"fingerprint": server.trusted_ssh_host_key_sha256}


async def _authenticate_websocket(
    token: str | None,
    session: AsyncSession,
    *,
    server_id: UUID,
    operation: str,
) -> User:
    if not token:
        raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)
    user = await _consume_remote_access_token(token, session, server_id=server_id, operation=operation)
    if user is None or not user.is_active:
        raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)
    if not user.is_superuser and ROLE_ORDER[user.role] < ROLE_ORDER[UserRole.OPERATOR]:
        raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)
    return user


async def _consume_remote_access_token(
    token: str,
    session: AsyncSession,
    *,
    server_id: UUID,
    operation: str,
) -> User | None:
    if "." not in token:
        raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)
    token_id, raw_token = token.split(".", 1)
    record = await RemoteAccessTokenRepository(session).get_by_token_id(token_id)
    now = datetime.now(UTC)
    if (
        record is None
        or record.server_id != server_id
        or record.operation != operation
        or record.consumed_at is not None
        or _aware_datetime(record.expires_at) <= now
        or record.token_hash != _hash_remote_token(raw_token)
    ):
        raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)
    record.consumed_at = now
    await session.commit()
    return await UserRepository(session).get_by_id(record.user_id)


def _access_payload_from_request(request: Request) -> dict[str, object] | None:
    authorization = request.headers.get("authorization", "")
    if not authorization.lower().startswith("bearer "):
        return None
    try:
        return decode_token(authorization.split(" ", 1)[1], expected_type="access")
    except TokenValidationError:
        return None


def _hash_remote_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def _aware_datetime(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


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
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[RemoteAccessService, Depends(get_remote_access_service)],
    user: Annotated[User, Depends(require_operator)],
    path: str = "/",
) -> RemoteDirectoryListing:
    try:
        result = await service.list_files(server_id, path, user)
        audit_remote_access_event("remote_file_listed", server_id=server_id, user=user, path=result.path)
        await audit_service_from_session(session).record(
            event_type="remote_access.file_listed",
            actor=user,
            target_type="server",
            target_id=server_id,
            result="success",
            source_ip=source_ip_from_request(request),
            metadata={"path": result.path},
        )
        return result
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/hosts/{server_id}/files/read", response_model=RemoteFileRead)
async def read_file(
    server_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[RemoteAccessService, Depends(get_remote_access_service)],
    user: Annotated[User, Depends(require_operator)],
    path: str,
) -> RemoteFileRead:
    try:
        result = await service.read_file(server_id, path, user)
        audit_remote_access_event("remote_file_read", server_id=server_id, user=user, path=result.path)
        await audit_service_from_session(session).record(
            event_type="remote_access.file_read",
            actor=user,
            target_type="server",
            target_id=server_id,
            result="success",
            source_ip=source_ip_from_request(request),
            metadata={"path": result.path},
        )
        return result
    except Exception as exc:
        raise _map_error(exc) from exc


@router.put("/hosts/{server_id}/files/write", response_model=RemoteFileWriteResponse)
async def write_file(
    server_id: UUID,
    payload: RemoteFileWriteRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[RemoteAccessService, Depends(get_remote_access_service)],
    user: Annotated[User, Depends(require_operator)],
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
        await audit_service_from_session(session).record(
            event_type="remote_access.file_write",
            actor=user,
            target_type="server",
            target_id=server_id,
            result="success",
            source_ip=source_ip_from_request(request),
            metadata={"path": result.path},
        )
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
        await audit_service_from_session(session).record(
            event_type="remote_access.file_write",
            actor=user,
            target_type="server",
            target_id=server_id,
            result="failed",
            source_ip=source_ip_from_request(request),
            metadata={"path": payload.path},
            error=exc.__class__.__name__,
        )
        raise _map_error(exc) from exc
