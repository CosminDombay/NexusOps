import pytest

from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.schemas import CredentialCreate
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.integrations.models import Integration, IntegrationProviderType, IntegrationType
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
                provider_type="proxmox",
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


def test_delete_integration_removes_record(client) -> None:
    create_response = client.post(
        "/api/v1/integrations",
        json={
            "name": "Prometheus Test",
            "type": "monitoring",
            "provider_type": "prometheus",
            "enabled": True,
            "config": {"url": "http://prometheus.example:9090", "verify_ssl": False},
            "credential_refs": {},
        },
    )
    assert create_response.status_code == 201
    integration_id = create_response.json()["id"]

    delete_response = client.delete(f"/api/v1/integrations/{integration_id}")

    assert delete_response.status_code == 204
    assert client.get("/api/v1/integrations").json() == []


def test_delete_missing_integration_returns_404(client) -> None:
    response = client.delete("/api/v1/integrations/11111111-1111-1111-1111-111111111111")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_integrations_includes_legacy_invalid_records(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        integration = Integration(
            name="Proxmox",
            type=IntegrationType.INFRASTRUCTURE_PROVIDER,
            provider_type=IntegrationProviderType.PROXMOX,
            enabled=True,
            config={"verify_ssl": False},
            credential_refs={},
        )
        db_session.add(integration)
        await db_session.commit()
        await db_session.refresh(integration)
        integration_id = str(integration.id)

    response = client.get("/api/v1/integrations")

    assert response.status_code == 200
    assert response.json()[0]["id"] == integration_id
    assert response.json()[0]["config"] == {"verify_ssl": False}
