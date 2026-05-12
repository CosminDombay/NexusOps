from enum import StrEnum
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class CommandStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CommandExecution(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "command_executions"

    server_id: Mapped[UUID] = mapped_column(ForeignKey("servers.id"), index=True)
    command: Mapped[str] = mapped_column(Text)
    user: Mapped[str] = mapped_column(String(100))
    exit_code: Mapped[int | None] = mapped_column(Integer)
    stdout: Mapped[str | None] = mapped_column(Text)
    stderr: Mapped[str | None] = mapped_column(Text)
    status: Mapped[CommandStatus] = mapped_column(Enum(CommandStatus), default=CommandStatus.PENDING)

