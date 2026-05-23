import structlog

from backend.app.db.session import AsyncSessionLocal
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.integrations.repository import IntegrationRepository
from backend.app.modules.integrations.service import IntegrationService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.monitoring.repository import MonitoringSnapshotRepository
from backend.app.modules.monitoring.service import MonitoringService

logger = structlog.get_logger(__name__)


async def validate_monitoring_snapshots() -> None:
    """Refresh lightweight monitoring snapshots without blocking API render paths."""
    async with AsyncSessionLocal() as session:
        service = MonitoringService(
            ServerRepository(session),
            integration_service=IntegrationService(
                IntegrationRepository(session),
                credential_service=CredentialService(repository=CredentialRepository(session)),
            ),
            snapshot_repository=MonitoringSnapshotRepository(session),
            credential_service=CredentialService(repository=CredentialRepository(session)),
        )
        result = await service.validate_all()
        logger.info(
            "monitoring_validation_completed",
            checked_servers=result.checked_servers,
            updated_servers=result.updated_servers,
            failed_servers=result.failed_servers,
        )
