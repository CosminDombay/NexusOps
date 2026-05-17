import pytest

from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.schemas import CredentialCreate
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.integrations.repository import IntegrationRepository
from backend.app.modules.integrations.schemas import IntegrationCreate
from backend.app.modules.integrations.service import IntegrationService


@pytest.mark.asyncio
async def test_proxmox_adapter_uses_enabled_integration_and_credential(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        credential_service = CredentialService(repository=CredentialRepository(db_session))
        credential = await credential_service.create_credential(
            CredentialCreate(
                name="pve-token",
                credential_type="api_token",
                username="root@pam!nexusops",
                secret="secret-value",
            )
        )
        integration_service = IntegrationService(
            IntegrationRepository(db_session),
            credential_service=credential_service,
        )
        await integration_service.create_integration(
            IntegrationCreate(
                name="Proxmox Lab",
                type="infrastructure_provider",
                enabled=True,
                config={"api_url": "https://pve.example:8006/api2/json", "verify_ssl": False},
                credential_refs={"token_secret": str(credential.id)},
            )
        )

        adapter = await integration_service.get_proxmox_adapter()

        assert adapter.api_url == "https://pve.example:8006/api2/json/"
        assert adapter.token_id == "root@pam!nexusops"
        assert adapter.token_secret == "secret-value"
        assert adapter.verify_ssl is False
