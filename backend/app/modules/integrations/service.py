from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

import httpx
import structlog

from backend.app.adapters.proxmox import HttpProxmoxAdapter, ProxmoxAdapterError
from backend.app.core.config import settings
from backend.app.modules.credentials.schemas import CredentialCreate
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.integrations.models import (
    Integration,
    IntegrationProviderType,
    IntegrationState,
    IntegrationType,
)
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


logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ProviderConnectionConfig:
    integration_id: UUID
    provider_type: IntegrationProviderType
    base_url: str
    verify_ssl: bool
    timeout_seconds: int
    headers: dict[str, str] = field(default_factory=dict)
    raw_config: dict[str, object] = field(default_factory=dict)


class IntegrationService:
    """Centralized platform integration configuration."""

    def __init__(self, repository: IntegrationRepository, credential_service: CredentialService | None = None) -> None:
        self.repository = repository
        self.credential_service = credential_service

    async def list_integrations(self) -> list[IntegrationRead]:
        return [IntegrationRead.model_validate(item) for item in await self.repository.list()]

    async def create_integration(self, payload: IntegrationCreate) -> IntegrationRead:
        data = payload.model_dump()
        if data.get("state") is None:
            data["state"] = IntegrationState.DISABLED if not data.get("enabled", True) else IntegrationState.DISCONNECTED
        integration = await self.repository.create(Integration(**data))
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
        if payload.enabled is False:
            integration.state = IntegrationState.DISABLED
        elif payload.enabled is True and integration.state == IntegrationState.DISABLED:
            integration.state = IntegrationState.DISCONNECTED
        await self.repository.session.commit()
        await self.repository.session.refresh(integration)
        return IntegrationRead.model_validate(integration)

    async def delete_integration(self, integration_id: UUID) -> None:
        integration = await self.repository.get_by_id(integration_id)
        if integration is None:
            raise IntegrationNotFoundError("Integration not found")
        integration.deleted_at = datetime.now(UTC)
        integration.enabled = False
        integration.state = IntegrationState.DISABLED
        await self.repository.session.commit()

    async def test_integration(self, integration_id: UUID) -> IntegrationTestRead:
        integration = await self.repository.get_by_id(integration_id)
        if integration is None:
            raise IntegrationNotFoundError("Integration not found")
        if not integration.enabled:
            await self.mark_integration_disabled(integration)
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

    async def list_enabled_providers(self, provider_type: IntegrationProviderType) -> list[Integration]:
        return await self.repository.list_enabled_by_provider(provider_type)

    async def bootstrap_default_proxmox_from_env(self) -> IntegrationRead | None:
        existing = await self.repository.list_by_type(IntegrationType.INFRASTRUCTURE_PROVIDER)
        if existing:
            logger.info("integration_bootstrap_skipped", reason="infrastructure_integrations_exist", count=len(existing))
            return None
        if not settings.proxmox_api_url or not settings.proxmox_token_id or not settings.proxmox_token_secret:
            logger.info("integration_bootstrap_skipped", reason="proxmox_env_incomplete")
            return None

        credential_refs: dict[str, str] = {}
        config: dict[str, object] = {
            "api_url": settings.proxmox_api_url,
            "token_id": settings.proxmox_token_id,
            "verify_ssl": settings.proxmox_verify_ssl,
            "timeout_seconds": settings.proxmox_timeout_seconds,
            "bootstrap_source": "env",
        }
        if self.credential_service is not None and settings.nexusops_master_key:
            credential = await self.credential_service.create_credential(
                CredentialCreate(
                    name="bootstrap-proxmox-token",
                    description="Bootstrapped from Proxmox environment values.",
                    credential_type="api_token",
                    username=settings.proxmox_token_id,
                    secret=settings.proxmox_token_secret,
                    tags=["bootstrap", "proxmox"],
                )
            )
            credential_refs["token_secret"] = str(credential.id)
            logger.info("integration_bootstrap_credential_created", credential_id=str(credential.id))
        else:
            config["token_secret"] = settings.proxmox_token_secret
            logger.warning(
                "integration_bootstrap_stored_secret_in_config",
                reason="nexusops_master_key_not_configured",
            )

        integration = await self.repository.create(
            Integration(
                name="Default Proxmox",
                type=IntegrationType.INFRASTRUCTURE_PROVIDER,
                provider_type=IntegrationProviderType.PROXMOX,
                enabled=True,
                state=IntegrationState.DISCONNECTED,
                config=config,
                credential_refs=credential_refs,
            )
        )
        await self.repository.session.commit()
        await self.repository.session.refresh(integration)
        logger.info("integration_bootstrap_created", integration_id=str(integration.id), provider_type="proxmox")
        return IntegrationRead.model_validate(integration)

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
            raw_config=integration.config,
        )

    async def get_proxmox_adapter(self, integration_id: UUID | None = None) -> HttpProxmoxAdapter:
        integration = await self.repository.get_by_id(integration_id) if integration_id else await self._active_proxmox_integration()
        if integration is None:
            raise IntegrationNotFoundError("No enabled Proxmox integration is configured")
        if integration.provider_type != IntegrationProviderType.PROXMOX:
            raise IntegrationNotFoundError("Proxmox integration not found")
        if not integration.enabled:
            raise IntegrationNotFoundError("Proxmox integration is disabled")

        token_secret, token_username = await self._secret_and_username(
            integration,
            "token_secret",
            None,
        )
        api_url = _str_config(integration, "api_url")
        token_id = _str_config(integration, "token_id") or token_username
        if not api_url or not token_id or not token_secret:
            raise IntegrationNotFoundError("Proxmox integration is missing API URL or token credentials")
        return HttpProxmoxAdapter(
            api_url=api_url,
            token_id=token_id,
            token_secret=token_secret,
            verify_ssl=_bool_config(integration, "verify_ssl", False),
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
            None,
        )
        api_url = _str_config(integration, "api_url")
        token_id = _str_config(integration, "token_id") or token_username
        if not api_url or not token_id or not token_secret:
            await self.mark_integration_error(integration, "Proxmox integration is missing API URL or token credentials")
            return IntegrationTestRead(
                integration_id=integration.id,
                status="error",
                message="Proxmox integration is missing API URL or token credentials.",
            )
        adapter = HttpProxmoxAdapter(
            api_url=api_url,
            token_id=token_id,
            token_secret=token_secret,
            verify_ssl=_bool_config(integration, "verify_ssl", False),
            timeout_seconds=_int_config(integration, "timeout_seconds", settings.proxmox_timeout_seconds),
        )
        try:
            nodes = await adapter.get_nodes()
        except ProxmoxAdapterError as exc:
            await self.mark_integration_error(integration, str(exc))
            return IntegrationTestRead(integration_id=integration.id, status="error", message=str(exc))
        await self.mark_integration_connected(integration)
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
            await self.mark_integration_error(integration, str(exc))
            return IntegrationTestRead(integration_id=integration.id, status="error", message=str(exc))
        await self.mark_integration_connected(integration)
        return IntegrationTestRead(integration_id=integration.id, status="ok", message="Connection test succeeded.")

    async def mark_integration_syncing(self, integration: Integration) -> None:
        integration.state = IntegrationState.SYNCING
        integration.last_error = None
        await self.repository.session.flush()

    async def mark_integration_connected(self, integration: Integration, *, commit: bool = True) -> None:
        integration.state = IntegrationState.CONNECTED
        integration.last_successful_sync = datetime.now(UTC)
        integration.last_error = None
        await self.repository.session.flush()
        if commit:
            await self.repository.session.commit()

    async def mark_integration_error(self, integration: Integration, error: str, *, commit: bool = True) -> None:
        integration.state = IntegrationState.ERROR
        integration.last_error = error
        await self.repository.session.flush()
        if commit:
            await self.repository.session.commit()

    async def mark_integration_disconnected(self, integration: Integration, error: str | None = None, *, commit: bool = True) -> None:
        integration.state = IntegrationState.DISCONNECTED
        integration.last_error = error
        await self.repository.session.flush()
        if commit:
            await self.repository.session.commit()

    async def mark_integration_disabled(self, integration: Integration, *, commit: bool = True) -> None:
        integration.state = IntegrationState.DISABLED
        await self.repository.session.flush()
        if commit:
            await self.repository.session.commit()

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
