from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, UuidPrimaryKeyMixin


class AuditEvent(Base, UuidPrimaryKeyMixin):
    __tablename__ = "audit_events"

    event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_username: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    target_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    result: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    workflow_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
