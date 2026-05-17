from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class AutomationScheduleType(StrEnum):
    INTERVAL = "interval"
    CRON = "cron"


class AutomationTargetMode(StrEnum):
    SINGLE_HOST = "single_host"
    MULTIPLE_HOSTS = "multiple_hosts"


class AutomationOperationType(StrEnum):
    ACTION = "action"
    PROFILE = "profile"
    PACKAGE = "package"
    DEPLOYMENT = "deployment"
    COMMAND = "command"


class Automation(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "automations"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    schedule_type: Mapped[AutomationScheduleType] = mapped_column(
        Enum(
            AutomationScheduleType,
            name="automation_schedule_type",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    cron_expression: Mapped[str | None] = mapped_column(String(120), nullable=True)
    interval_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_mode: Mapped[AutomationTargetMode] = mapped_column(
        Enum(
            AutomationTargetMode,
            name="automation_target_mode",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    target_server_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    operation_type: Mapped[AutomationOperationType] = mapped_column(
        Enum(
            AutomationOperationType,
            name="automation_operation_type",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        index=True,
    )
    reference_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_command: Mapped[str | None] = mapped_column(Text, nullable=True)
    variables_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    credential_refs: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
