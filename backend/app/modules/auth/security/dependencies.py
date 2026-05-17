from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db_session
from backend.app.modules.auth.models import User, UserRole
from backend.app.modules.auth.repositories.user_repository import UserRepository
from backend.app.modules.auth.security.jwt import TokenValidationError, decode_token

bearer_scheme = HTTPBearer(auto_error=False)

ROLE_ORDER = {
    UserRole.VIEWER: 1,
    UserRole.OPERATOR: 2,
    UserRole.ADMIN: 3,
}


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except TokenValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = await UserRepository(session).get_by_id(UUID(str(payload["sub"])))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is inactive or no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(minimum_role: UserRole):
    async def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.is_superuser or ROLE_ORDER[user.role] >= ROLE_ORDER[minimum_role]:
            return user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    return dependency


require_admin = require_role(UserRole.ADMIN)
require_operator = require_role(UserRole.OPERATOR)
require_viewer = require_role(UserRole.VIEWER)
