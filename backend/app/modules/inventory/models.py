from enum import StrEnum

from sqlalchemy import JSON, Enum, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class ServerStatus(StrEnum):
    UNKNOWN = "unknown"
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class ServerEnvironment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"
    LAB = "lab"


class ServerSshAuthMethod(StrEnum):
    KEY = "key"
    PASSWORD = "password"


class Server(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "servers"
    __table_args__ = (
        UniqueConstraint("hostname", name="uq_servers_hostname"),
        UniqueConstraint("ip_address", name="uq_servers_ip_address"),
    )

    hostname: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    ip_address: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    operating_system: Mapped[str] = mapped_column(String(150), nullable=False)
    vmid: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    environment: Mapped[ServerEnvironment] = mapped_column(
        Enum(ServerEnvironment, name="server_environment"),
        nullable=False,
        index=True,
    )
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    ssh_port: Mapped[int] = mapped_column(Integer, default=22, nullable=False)
    ssh_username: Mapped[str] = mapped_column(String(100), nullable=False)
    ssh_auth_method: Mapped[ServerSshAuthMethod] = mapped_column(
        Enum(
            ServerSshAuthMethod,
            name="server_ssh_auth_method",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=ServerSshAuthMethod.KEY,
        nullable=False,
    )
    ssh_password: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ssh_private_key_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[ServerStatus] = mapped_column(
        Enum(ServerStatus),
        default=ServerStatus.UNKNOWN,
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
