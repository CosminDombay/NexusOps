from uuid import UUID

import structlog

from backend.app.modules.auth.models import User

logger = structlog.get_logger(__name__)


def audit_remote_access_event(
    event: str,
    *,
    server_id: UUID,
    user: User | None,
    path: str | None = None,
    outcome: str = "success",
    reason: str | None = None,
) -> None:
    payload: dict[str, object | None] = {
        "server_id": str(server_id),
        "user_id": str(user.id) if user and user.id else None,
        "username": user.username if user else None,
        "role": user.role.value if user else None,
        "path": path,
        "outcome": outcome,
    }
    if reason:
        payload["reason"] = reason
    logger.info(event, **payload)
