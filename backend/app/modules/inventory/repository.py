from uuid import UUID

from sqlalchemy import delete, or_, select

from backend.app.common.repository import BaseRepository
from backend.app.modules.inventory.models import InventoryLifecycleState, Server, ServerEnvironment


INACTIVE_LIFECYCLE_STATES = {
    InventoryLifecycleState.ARCHIVED,
    InventoryLifecycleState.DECOMMISSIONED,
    InventoryLifecycleState.DELETED,
}


class ServerRepository(BaseRepository[Server]):
    async def create(self, server: Server) -> Server:
        self.session.add(server)
        await self.session.flush()
        await self.session.refresh(server)
        return server

    async def get_by_id(self, server_id: UUID) -> Server | None:
        result = await self.session.execute(select(Server).where(Server.id == server_id))
        return result.scalar_one_or_none()

    async def get_by_hostname(self, hostname: str) -> Server | None:
        result = await self.session.execute(select(Server).where(Server.hostname == hostname))
        return result.scalar_one_or_none()

    async def get_by_ip_address(self, ip_address: str) -> Server | None:
        result = await self.session.execute(select(Server).where(Server.ip_address == ip_address))
        return result.scalar_one_or_none()

    async def get_by_provider_external_id(self, provider: str, external_id: str) -> Server | None:
        result = await self.session.execute(
            select(Server).where(Server.provider == provider, Server.external_id == external_id)
        )
        return result.scalar_one_or_none()

    async def get_by_provider_external_id_for_integration(
        self,
        provider: str,
        external_id: str,
        integration_id: UUID | None,
    ) -> Server | None:
        query = select(Server).where(Server.provider == provider, Server.external_id == external_id)
        if integration_id is None:
            query = query.where(Server.integration_id.is_(None))
        else:
            query = query.where(Server.integration_id == integration_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_provider(self, provider: str) -> list[Server]:
        result = await self.session.execute(select(Server).where(Server.provider == provider))
        return list(result.scalars().all())

    async def list_by_provider_integration(
        self,
        provider: str,
        integration_id: UUID | None,
    ) -> list[Server]:
        query = select(Server).where(Server.provider == provider)
        if integration_id is None:
            query = query.where(Server.integration_id.is_(None))
        else:
            query = query.where(Server.integration_id == integration_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list(
        self,
        *,
        environment: ServerEnvironment | None = None,
        provider: str | None = None,
        integration_id: UUID | None = None,
        cluster: str | None = None,
        search: str | None = None,
        include_inactive: bool = False,
    ) -> list[Server]:
        query = select(Server).order_by(Server.created_at.desc())

        if environment is not None:
            query = query.where(Server.environment == environment)

        if provider:
            query = query.where(Server.provider == provider)

        if integration_id is not None:
            query = query.where(Server.integration_id == integration_id)

        if cluster:
            query = query.where(Server.provider_node == cluster)

        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    Server.hostname.ilike(pattern),
                    Server.ip_address.ilike(pattern),
                    Server.external_id.ilike(pattern),
                )
            )

        if not include_inactive:
            query = query.where(Server.lifecycle_state.not_in(INACTIVE_LIFECYCLE_STATES))

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def delete(self, server: Server) -> None:
        await self.session.execute(delete(Server).where(Server.id == server.id))
