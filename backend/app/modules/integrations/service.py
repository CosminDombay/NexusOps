from uuid import UUID

import httpx

from backend.app.adapters.proxmox import HttpProxmoxAdapter, ProxmoxAdapterError
from backend.app.core.config import settings
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.integrations.models import Integration
from backend.app.modules.integrations.repository import IntegrationRepository
from backend.app.modules.integrations.schemas import (
    IntegrationCreate,
    IntegrationRead,
    IntegrationTestRead,
    IntegrationUpdate,
)


class IntegrationNotFoundError(Exception):
    """Raised when an integration cannot be found."""


class IntegrationService:
    """Centralized platform integration configuration."""

    def __init__(self, repository: IntegrationRepository, credential_service: CredentialService | None = None) -> None:
        self.repository = repository
        self.credential_service = credential_service

    async def list_integrations(self) -> list[IntegrationRead]:
        return [IntegrationRead.model_validate(item) for item in await self.repository.list()]

    async def create_integration(self, payload: IntegrationCreate) -> IntegrationRead:
        integration = await self.repository.create(Integration(**payload.model_dump()))
        await self.repository.session.commit()
        return IntegrationRead.model_validate(integration)

    async def update_integration(self, integration_id: UUID, payload: IntegrationUpdate) -> IntegrationRead:
        integration = await self.repository.get_by_id(integration_id)
        if integration is None:
            raise IntegrationNotFoundError("Integration not found")
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(integration, key, value)
        await self.repository.session.commit()
        await self.repository.session.refresh(integration)
        return IntegrationRead.model_validate(integration)

    async def test_integration(self, integration_id: UUID) -> IntegrationTestRead:
        integration = await self.repository.get_by_id(integration_id)
        if integration is None:
            raise IntegrationNotFoundError("Integration not found")
        if not integration.enabled:
            return IntegrationTestRead(
                integration_id=integration.id,
                status="disabled",
                message="Integration is disabled.",
            )
        name = integration.name.lower()
        if "proxmox" in name:
            return await self._test_proxmox(integration)
        if "prometheus" in name:
            return await self._test_http(integration, default_url=settings.prometheus_api_url, suffix="/-/healthy")
        if "grafana" in name:
            return await self._test_http(integration, default_url=settings.grafana_base_url, suffix="/api/health")
        return IntegrationTestRead(
            integration_id=integration.id,
            status="unknown",
            message="No connection test is defined for this integration yet.",
        )

    async def _test_proxmox(self, integration: Integration) -> IntegrationTestRead:
        adapter = HttpProxmoxAdapter(
            api_url=_str_config(integration, "api_url") or settings.proxmox_api_url,
            token_id=_str_config(integration, "token_id") or settings.proxmox_token_id,
            token_secret=await self._secret_config(integration, "token_secret", settings.proxmox_token_secret),
            verify_ssl=_bool_config(integration, "verify_ssl", settings.proxmox_verify_ssl),
        )
        try:
            nodes = await adapter.get_nodes()
        except ProxmoxAdapterError as exc:
            return IntegrationTestRead(integration_id=integration.id, status="error", message=str(exc))
        return IntegrationTestRead(
            integration_id=integration.id,
            status="ok",
            message=f"Connected to Proxmox. {len(nodes)} node(s) visible.",
        )

    async def _test_http(self, integration: Integration, *, default_url: str | None, suffix: str) -> IntegrationTestRead:
        base_url = (_str_config(integration, "url") or _str_config(integration, "base_url") or default_url or "").rstrip("/")
        if not base_url:
            return IntegrationTestRead(integration_id=integration.id, status="error", message="No URL configured.")
        try:
            async with httpx.AsyncClient(timeout=settings.monitoring_timeout_seconds) as client:
                headers = {}
                bearer_token = await self._secret_config(integration, "bearer_token", None)
                api_token = await self._secret_config(integration, "api_token", None)
                if bearer_token or api_token:
                    headers["Authorization"] = f"Bearer {bearer_token or api_token}"
                response = await client.get(f"{base_url}{suffix}", headers=headers)
                response.raise_for_status()
        except Exception as exc:
            return IntegrationTestRead(integration_id=integration.id, status="error", message=str(exc))
        return IntegrationTestRead(integration_id=integration.id, status="ok", message="Connection test succeeded.")

    async def _secret_config(self, integration: Integration, key: str, default: str | None) -> str | None:
        credential_ref = (integration.credential_refs or {}).get(key)
        if not credential_ref:
            return _str_config(integration, key) or default
        if self.credential_service is None:
            return default
        credential = await self.credential_service.resolve_credential(credential_ref)
        return credential.secret or credential.private_key or default


def _str_config(integration: Integration, key: str) -> str | None:
    value = integration.config.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _bool_config(integration: Integration, key: str, default: bool) -> bool:
    value = integration.config.get(key)
    return value if isinstance(value, bool) else default
