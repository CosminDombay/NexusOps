from dataclasses import dataclass, field
from uuid import UUID

import httpx

from backend.app.adapters.proxmox import HttpProxmoxAdapter, ProxmoxAdapterError
from backend.app.core.config import settings
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.integrations.models import Integration, IntegrationProviderType
from backend.app.modules.integrations.repository import IntegrationRepository
from backend.app.modules.integrations.schemas import (
    IntegrationCreate,
    IntegrationRead,
    IntegrationTestRead,
    IntegrationUpdate,
    validate_integration_config,
)


class IntegrationNotFoundError(Exception):
    """Raised when an integration cannot be found."""


@dataclass(frozen=True)
class ProviderConnectionConfig:
    integration_id: UUID
    provider_type: IntegrationProviderType
    base_url: str
    verify_ssl: bool
    timeout_seconds: int
    headers: dict[str, str] = field(default_factory=dict)


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
        validate_integration_config(
            payload.provider_type or integration.provider_type,
            payload.config if payload.config is not None else integration.config,
        )
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(integration, key, value)
        await self.repository.session.commit()
        await self.repository.session.refresh(integration)
        return IntegrationRead.model_validate(integration)

    async def delete_integration(self, integration_id: UUID) -> None:
        integration = await self.repository.get_by_id(integration_id)
        if integration is None:
            raise IntegrationNotFoundError("Integration not found")
        await self.repository.delete(integration)
        await self.repository.session.commit()

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
        if integration.provider_type == IntegrationProviderType.PROXMOX:
            return await self._test_proxmox(integration)
        if integration.provider_type == IntegrationProviderType.PROMETHEUS:
            return await self._test_http(integration, default_url=settings.prometheus_api_url, suffix="/-/healthy")
        if integration.provider_type == IntegrationProviderType.GRAFANA:
            return await self._test_http(integration, default_url=settings.grafana_base_url, suffix="/api/health")
        return IntegrationTestRead(
            integration_id=integration.id,
            status="unknown",
            message="No connection test is defined for this integration yet.",
        )

    async def get_enabled_provider(self, provider_type: IntegrationProviderType) -> Integration | None:
        integrations = await self.repository.list_enabled_by_provider(provider_type)
        return integrations[0] if integrations else None

    async def get_provider_connection_config(
        self,
        provider_type: IntegrationProviderType,
        *,
        default_timeout_seconds: int,
    ) -> ProviderConnectionConfig | None:
        integration = await self.get_enabled_provider(provider_type)
        if integration is None:
            return None
        base_url = _base_url_config(integration)
        if not base_url:
            return None
        headers = await self._auth_headers(integration)
        return ProviderConnectionConfig(
            integration_id=integration.id,
            provider_type=provider_type,
            base_url=base_url.rstrip("/"),
            verify_ssl=_bool_config(integration, "verify_ssl", True),
            timeout_seconds=_int_config(integration, "timeout_seconds", default_timeout_seconds),
            headers=headers,
        )

    async def get_proxmox_adapter(self) -> HttpProxmoxAdapter:
        integration = await self._active_proxmox_integration()
        if integration is None:
            return HttpProxmoxAdapter()

        token_secret, token_username = await self._secret_and_username(
            integration,
            "token_secret",
            settings.proxmox_token_secret,
        )
        return HttpProxmoxAdapter(
            api_url=_str_config(integration, "api_url") or settings.proxmox_api_url,
            token_id=(
                _str_config(integration, "token_id")
                or token_username
                or settings.proxmox_token_id
            ),
            token_secret=token_secret,
            verify_ssl=_bool_config(integration, "verify_ssl", settings.proxmox_verify_ssl),
            timeout_seconds=_int_config(
                integration,
                "timeout_seconds",
                settings.proxmox_timeout_seconds,
            ),
        )

    async def _active_proxmox_integration(self) -> Integration | None:
        return await self.get_enabled_provider(IntegrationProviderType.PROXMOX)

    async def _test_proxmox(self, integration: Integration) -> IntegrationTestRead:
        token_secret, token_username = await self._secret_and_username(
            integration,
            "token_secret",
            settings.proxmox_token_secret,
        )
        adapter = HttpProxmoxAdapter(
            api_url=_str_config(integration, "api_url") or settings.proxmox_api_url,
            token_id=_str_config(integration, "token_id") or token_username or settings.proxmox_token_id,
            token_secret=token_secret,
            verify_ssl=_bool_config(integration, "verify_ssl", settings.proxmox_verify_ssl),
            timeout_seconds=_int_config(integration, "timeout_seconds", settings.proxmox_timeout_seconds),
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
        base_url = (_base_url_config(integration) or default_url or "").rstrip("/")
        if not base_url:
            return IntegrationTestRead(integration_id=integration.id, status="error", message="No URL configured.")
        try:
            async with httpx.AsyncClient(
                timeout=_int_config(integration, "timeout_seconds", settings.monitoring_timeout_seconds),
                verify=_bool_config(integration, "verify_ssl", True),
            ) as client:
                response = await client.get(f"{base_url}{suffix}", headers=await self._auth_headers(integration))
                response.raise_for_status()
        except Exception as exc:
            return IntegrationTestRead(integration_id=integration.id, status="error", message=str(exc))
        return IntegrationTestRead(integration_id=integration.id, status="ok", message="Connection test succeeded.")

    async def _auth_headers(self, integration: Integration) -> dict[str, str]:
        bearer_token = await self._secret_config(integration, "bearer_token", None)
        api_token = await self._secret_config(integration, "api_token", None)
        if bearer_token or api_token:
            return {"Authorization": f"Bearer {bearer_token or api_token}"}
        return {}

    async def _secret_config(self, integration: Integration, key: str, default: str | None) -> str | None:
        secret, _username = await self._secret_and_username(integration, key, default)
        return secret

    async def _secret_and_username(
        self,
        integration: Integration,
        key: str,
        default: str | None,
    ) -> tuple[str | None, str | None]:
        credential_ref = (integration.credential_refs or {}).get(key)
        if not credential_ref:
            return _str_config(integration, key) or default, None
        if self.credential_service is None:
            return default, None
        credential = await self.credential_service.resolve_credential(credential_ref)
        return credential.secret or credential.private_key or default, credential.username


def _str_config(integration: Integration, key: str) -> str | None:
    value = integration.config.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _base_url_config(integration: Integration) -> str | None:
    return (
        _str_config(integration, "api_url")
        or _str_config(integration, "url")
        or _str_config(integration, "base_url")
    )


def _bool_config(integration: Integration, key: str, default: bool) -> bool:
    value = integration.config.get(key)
    return value if isinstance(value, bool) else default


def _int_config(integration: Integration, key: str, default: int) -> int:
    value = integration.config.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default
