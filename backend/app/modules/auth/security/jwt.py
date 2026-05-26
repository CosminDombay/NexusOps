from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from jose import JWTError, jwt

from backend.app.core.config import settings
from backend.app.modules.auth.models import User, UserRole

TokenType = Literal["access", "refresh"]


class TokenValidationError(Exception):
    pass


def create_token(
    user: User,
    *,
    token_type: TokenType,
    expires_delta: timedelta,
    token_id: str | None = None,
    family_id: str | None = None,
    session_id: UUID | None = None,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role.value,
        "ver": user.token_version,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if token_id:
        payload["jti"] = token_id
    if family_id:
        payload["family"] = family_id
    if session_id:
        payload["sid"] = str(session_id)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user: User, *, session_id: UUID | None = None) -> str:
    return create_token(
        user,
        token_type="access",
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        session_id=session_id,
    )


def create_refresh_token(user: User, *, token_id: str, family_id: str, session_id: UUID) -> str:
    return create_token(
        user,
        token_type="refresh",
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
        token_id=token_id,
        family_id=family_id,
        session_id=session_id,
    )


def decode_token(token: str, *, expected_type: TokenType) -> dict[str, object]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise TokenValidationError("Invalid token") from exc

    if payload.get("type") != expected_type:
        raise TokenValidationError("Invalid token type")

    if not payload.get("sub") or not payload.get("username") or not payload.get("role"):
        raise TokenValidationError("Invalid token payload")

    try:
        UUID(str(payload["sub"]))
        UserRole(str(payload["role"]))
        int(payload.get("ver"))
    except (ValueError, TypeError) as exc:
        raise TokenValidationError("Invalid token payload") from exc

    return payload
