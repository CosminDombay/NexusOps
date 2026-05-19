import asyncio
from collections import Counter
from datetime import UTC, datetime
from uuid import UUID

import structlog

from backend.app.common.constants import InventoryHealthStatus, InventoryLifecycleState
from backend.app.modules.inventory.models import Server
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.schemas import InventoryHealthCheckResult, InventoryHealthSummary
from backend.app.modules.inventory.service import ServerNotFoundError

logger = structlog.get_logger(__name__)


class InventoryHealthService:
    """Lightweight inventory reachability checks.

    Health checks intentionally validate only TCP connectivity to the configured SSH
    port. Full SSH authentication is reserved for Jobs and future deeper checks.
    """

    def __init__(self, repository: ServerRepository, *, timeout_seconds: float = 3.0) -> None:
        self.repository = repository
        self.timeout_seconds = timeout_seconds

    async def check_server(self, server_id: UUID) -> InventoryHealthCheckResult:
        server = await self.repository.get_by_id(server_id)
        if server is None:
            raise ServerNotFoundError("Server not found")
        return await self._check_and_update(server)

    async def check_bulk(self, server_ids: list[UUID] | None = None) -> list[InventoryHealthCheckResult]:
        servers = await self.repository.list()
        if server_ids is not None:
            selected = set(server_ids)
            servers = [server for server in servers if server.id in selected]

        results: list[InventoryHealthCheckResult] = []
        for server in servers:
            try:
                results.append(await self._check_and_update(server))
            except Exception as exc:
                logger.warning(
                    "inventory_health_check_failed_unexpected",
                    server_id=str(server.id),
                    hostname=server.hostname,
                    reason=str(exc),
                )
                results.append(await self._mark_error(server, str(exc)))
        return results

    async def summary(self) -> InventoryHealthSummary:
        servers = await self.repository.list()
        statuses = Counter(server.last_health_status for server in servers)
        last_checked = max(
            (server.last_health_check_at for server in servers if server.last_health_check_at),
            default=None,
        )
        return InventoryHealthSummary(
            total=len(servers),
            online=statuses[InventoryHealthStatus.ONLINE],
            unreachable=statuses[InventoryHealthStatus.UNREACHABLE],
            unknown=statuses[InventoryHealthStatus.UNKNOWN],
            provisioning=statuses[InventoryHealthStatus.PROVISIONING],
            archived=statuses[InventoryHealthStatus.ARCHIVED],
            sync_error=statuses[InventoryHealthStatus.SYNC_ERROR],
            last_checked_at=last_checked,
        )

    async def _check_and_update(self, server: Server) -> InventoryHealthCheckResult:
        checked_at = datetime.now(UTC)
        if server.lifecycle_state in {
            InventoryLifecycleState.ARCHIVED,
            InventoryLifecycleState.DECOMMISSIONED,
            InventoryLifecycleState.DELETED,
        }:
            return await self._apply_result(
                server,
                status=InventoryHealthStatus.ARCHIVED,
                checked_at=checked_at,
                error=None,
            )
        if server.lifecycle_state == InventoryLifecycleState.PROVISIONED and not server.managed:
            return await self._apply_result(
                server,
                status=InventoryHealthStatus.PROVISIONING,
                checked_at=checked_at,
                error=None,
            )

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(server.ip_address, server.ssh_port),
                timeout=self.timeout_seconds,
            )
            writer.close()
            await writer.wait_closed()
            return await self._apply_result(
                server,
                status=InventoryHealthStatus.ONLINE,
                checked_at=checked_at,
                error=None,
            )
        except (TimeoutError, OSError, ConnectionError) as exc:
            return await self._apply_result(
                server,
                status=InventoryHealthStatus.UNREACHABLE,
                checked_at=checked_at,
                error=str(exc)[:500],
            )

    async def _mark_error(self, server: Server, error: str) -> InventoryHealthCheckResult:
        return await self._apply_result(
            server,
            status=InventoryHealthStatus.SYNC_ERROR,
            checked_at=datetime.now(UTC),
            error=error[:500],
        )

    async def _apply_result(
        self,
        server: Server,
        *,
        status: InventoryHealthStatus,
        checked_at: datetime,
        error: str | None,
    ) -> InventoryHealthCheckResult:
        server.last_health_status = status
        server.last_health_check_at = checked_at
        server.last_health_error = error
        await self.repository.session.commit()
        await self.repository.session.refresh(server)
        return InventoryHealthCheckResult(
            server_id=server.id,
            hostname=server.hostname,
            status=status,
            checked_at=checked_at,
            error=error,
        )
