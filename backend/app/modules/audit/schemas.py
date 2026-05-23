from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AuditEventRead(BaseModel):
    id: UUID
    event_type: str
    actor_user_id: UUID | None = None
    actor_username: str | None = None
    occurred_at: datetime
    target_type: str | None = None
    target_id: str | None = None
    result: str
    metadata_json: dict[str, object] = Field(default_factory=dict)
    source_ip: str | None = None
    correlation_id: str | None = None
    workflow_run_id: UUID | None = None
    error: str | None = None

    model_config = {"from_attributes": True}
