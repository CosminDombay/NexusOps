from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError

from backend.app.modules.inventory.models import Server, ServerEnvironment
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.schemas import ServerCreate, ServerUpdate

logger = structlog.get_logger(__name__)


class InventoryConflictError(Exception):
    """Raised when a server violates inventory uniqueness rules."""


class ServerNotFoundError(Exception):
    """Raised when a server does not exist."""


class InventoryService:
    """Application service for server inventory workflows."""

    def __init__(self, repository: ServerRepository) -> None:
        self.repository = repository

    async def create_server(self, payload: ServerCreate) -> Server:
        await self._ensure_unique(hostname=payload.hostname, ip_address=payload.ip_address)

        server = Server(**payload.model_dump())
        try:
            created = await self.repository.create(server)
            await self.repository.session.commit()
        except IntegrityError as exc:
            await self.repository.session.rollback()
            logger.warning(
                "server_create_failed",
                hostname=payload.hostname,
                ip_address=payload.ip_address,
                reason="integrity_error",
            )
            raise InventoryConflictError("Hostname or IP address already exists") from exc

        logger.info(
            "server_created",
            server_id=str(created.id),
            hostname=created.hostname,
            ip_address=created.ip_address,
            environment=created.environment,
            provider=created.provider,
        )
        return created

    async def update_server(self, server_id: UUID, payload: ServerUpdate) -> Server:
        server = await self.repository.get_by_id(server_id)
        if server is None:
            logger.warning("server_update_failed", server_id=str(server_id), reason="not_found")
            raise ServerNotFoundError("Server not found")

        update_data = payload.model_dump(exclude_unset=True)
        await self._ensure_unique(
            hostname=update_data.get("hostname"),
            ip_address=update_data.get("ip_address"),
            exclude_id=server_id,
        )

        for key, value in update_data.items():
            setattr(server, key, value)

        try:
            await self.repository.session.flush()
            await self.repository.session.refresh(server)
            await self.repository.session.commit()
        except IntegrityError as exc:
            await self.repository.session.rollback()
            logger.warning("server_update_failed", server_id=str(server_id), reason="integrity_error")
            raise InventoryConflictError("Hostname or IP address already exists") from exc

        logger.info("server_updated", server_id=str(server.id), fields=list(update_data.keys()))
        return server

    async def delete_server(self, server_id: UUID) -> None:
        server = await self.repository.get_by_id(server_id)
        if server is None:
            logger.warning("server_delete_failed", server_id=str(server_id), reason="not_found")
            raise ServerNotFoundError("Server not found")

        await self.repository.delete(server)
        await self.repository.session.commit()
        logger.info("server_deleted", server_id=str(server_id), hostname=server.hostname)

    async def get_server(self, server_id: UUID) -> Server:
        server = await self.repository.get_by_id(server_id)
        if server is None:
            raise ServerNotFoundError("Server not found")
        return server

    async def list_servers(
        self,
        *,
        environment: ServerEnvironment | None = None,
        provider: str | None = None,
        search: str | None = None,
    ) -> list[Server]:
        return await self.repository.list(environment=environment, provider=provider, search=search)

    async def _ensure_unique(
        self,
        *,
        hostname: str | None = None,
        ip_address: str | None = None,
        exclude_id: UUID | None = None,
    ) -> None:
        if hostname:
            existing = await self.repository.get_by_hostname(hostname)
            if existing and existing.id != exclude_id:
                logger.warning("server_validation_failed", hostname=hostname, reason="hostname_exists")
                raise InventoryConflictError("Hostname already exists")

        if ip_address:
            existing = await self.repository.get_by_ip_address(ip_address)
            if existing and existing.id != exclude_id:
                logger.warning("server_validation_failed", ip_address=ip_address, reason="ip_exists")
                raise InventoryConflictError("IP address already exists")
