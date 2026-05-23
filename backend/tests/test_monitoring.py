from datetime import UTC, datetime, timedelta
from uuid import UUID

from backend.app.adapters.ssh import SshExecutionResult
from backend.tests.test_inventory import server_payload


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None


class _FakeHttpClient:
    calls: list[str] = []
    fail = False

    def __init__(self, *args, **kwargs) -> None:
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def get(self, url, **kwargs):
        self.calls.append(url)
        if self.fail:
            raise TimeoutError("monitoring unavailable")
        return _FakeResponse()


class _FakeWriter:
    def close(self) -> None:
        return None

    async def wait_closed(self) -> None:
        return None


async def _fake_open_connection(host, port):
    if port in {9100, 9080}:
        return object(), _FakeWriter()
    raise OSError("connection refused")


async def _fake_open_connection_all_down(host, port):
    raise OSError("connection refused")


async def _fake_systemctl_node_promtail(self, **kwargs):
    command = kwargs["command"]
    if "node_exporter" in command or "node-exporter" in command or "promtail" in command:
        return SshExecutionResult(exit_code=0, stdout="active\n", stderr="")
    return SshExecutionResult(exit_code=3, stdout="inactive\n", stderr="")


async def _fake_systemctl_all_down(self, **kwargs):
    return SshExecutionResult(exit_code=3, stdout="inactive\n", stderr="")


async def _fake_systemctl_all_up(self, **kwargs):
    return SshExecutionResult(exit_code=0, stdout="active\n", stderr="")


async def _fake_cadvisor_docker_ps(self, **kwargs):
    command = kwargs["command"]
    if "systemctl" in command:
        return SshExecutionResult(exit_code=3, stdout="inactive\n", stderr="")
    if "docker ps" in command and "cadvisor" in command:
        return SshExecutionResult(exit_code=0, stdout="cadvisor gcr.io/cadvisor/cadvisor\n", stderr="")
    return SshExecutionResult(exit_code=1, stdout="", stderr="")


def _create_monitoring_integrations(client) -> None:
    assert client.post(
        "/api/v1/integrations",
        json={
            "name": "Metrics provider",
            "type": "monitoring",
            "provider_type": "prometheus",
            "enabled": True,
            "config": {"url": "http://prometheus.internal:9090", "verify_ssl": False, "timeout_seconds": 7},
            "credential_refs": {},
        },
    ).status_code == 201
    assert client.post(
        "/api/v1/integrations",
        json={
            "name": "Grafana",
            "type": "monitoring",
            "provider_type": "grafana",
            "enabled": True,
            "config": {
                "base_url": "https://grafana.example",
                "dashboard_uid_template": "node-${hostname}",
                "dashboard_slug_template": "linux-node",
            },
            "credential_refs": {},
        },
    ).status_code == 201


def test_monitoring_overview_uses_persisted_snapshots_only(client, monkeypatch) -> None:
    _FakeHttpClient.calls = []
    monkeypatch.setattr("backend.app.modules.monitoring.service.httpx.AsyncClient", _FakeHttpClient)
    monkeypatch.setattr("backend.app.modules.monitoring.service.asyncio.open_connection", _fake_open_connection)
    monkeypatch.setattr("backend.app.modules.monitoring.service.ParamikoSshAdapter.run_command", _fake_systemctl_node_promtail)
    _create_monitoring_integrations(client)
    assert client.post(
        "/api/v1/servers",
        json=server_payload(hostname="hds-tool", ip_address="192.168.50.15"),
    ).status_code == 201

    initial = client.get("/api/v1/monitoring/overview")
    assert initial.status_code == 200
    assert initial.json()["servers"][0]["monitoring_state"] == "unknown"
    assert _FakeHttpClient.calls == []

    validate = client.post("/api/v1/monitoring/validate")
    assert validate.status_code == 200
    assert validate.json()["checked_servers"] == 1
    assert _FakeHttpClient.calls == ["http://prometheus.internal:9090/-/healthy"]

    _FakeHttpClient.calls = []
    overview = client.get("/api/v1/monitoring/overview")
    assert overview.status_code == 200
    payload = overview.json()
    assert _FakeHttpClient.calls == []
    server = payload["servers"][0]
    assert server["monitoring_state"] == "partial"
    assert server["node_exporter_status"] == "healthy"
    assert server["promtail_status"] == "healthy"
    assert server["cadvisor_status"] == "unavailable"
    assert server["prometheus_target_health"] == "healthy"
    assert server["open_grafana_url"].startswith("https://grafana.example/d/node-hds-tool/linux-node?")


def test_monitoring_marks_unavailable_exporters_unmonitored(client, monkeypatch) -> None:
    monkeypatch.setattr("backend.app.modules.monitoring.service.httpx.AsyncClient", _FakeHttpClient)
    monkeypatch.setattr("backend.app.modules.monitoring.service.asyncio.open_connection", _fake_open_connection_all_down)
    monkeypatch.setattr("backend.app.modules.monitoring.service.ParamikoSshAdapter.run_command", _fake_systemctl_all_down)
    _create_monitoring_integrations(client)
    assert client.post("/api/v1/servers", json=server_payload()).status_code == 201

    assert client.post("/api/v1/monitoring/validate").status_code == 200
    server = client.get("/api/v1/monitoring/overview").json()["servers"][0]

    assert server["monitoring_state"] == "unmonitored"
    assert server["node_exporter_status"] == "unavailable"
    assert server["promtail_status"] == "unavailable"
    assert server["cadvisor_status"] == "unavailable"


def test_monitoring_overview_ignores_unmanaged_inventory_nodes(client, monkeypatch) -> None:
    monkeypatch.setattr("backend.app.modules.monitoring.service.httpx.AsyncClient", _FakeHttpClient)
    monkeypatch.setattr("backend.app.modules.monitoring.service.asyncio.open_connection", _fake_open_connection)
    monkeypatch.setattr("backend.app.modules.monitoring.service.ParamikoSshAdapter.run_command", _fake_systemctl_node_promtail)
    _create_monitoring_integrations(client)
    create_response = client.post("/api/v1/servers", json=server_payload())
    assert create_response.status_code == 201
    server_id = create_response.json()["id"]
    assert client.post(f"/api/v1/servers/{server_id}/unmanage").status_code == 200

    validate = client.post("/api/v1/monitoring/validate")
    overview = client.get("/api/v1/monitoring/overview")

    assert validate.status_code == 200
    assert validate.json()["checked_servers"] == 0
    assert overview.status_code == 200
    assert overview.json()["servers"] == []


def test_monitoring_preserves_snapshot_when_monitoring_infrastructure_fails(client, monkeypatch) -> None:
    _FakeHttpClient.fail = False
    monkeypatch.setattr("backend.app.modules.monitoring.service.httpx.AsyncClient", _FakeHttpClient)
    monkeypatch.setattr("backend.app.modules.monitoring.service.asyncio.open_connection", _fake_open_connection)
    monkeypatch.setattr("backend.app.modules.monitoring.service.ParamikoSshAdapter.run_command", _fake_systemctl_node_promtail)
    _create_monitoring_integrations(client)
    assert client.post("/api/v1/servers", json=server_payload()).status_code == 201
    assert client.post("/api/v1/monitoring/validate").status_code == 200

    _FakeHttpClient.fail = True
    assert client.post("/api/v1/monitoring/validate").status_code == 200
    server = client.get("/api/v1/monitoring/overview").json()["servers"][0]
    _FakeHttpClient.fail = False

    assert server["node_exporter_status"] == "healthy"
    assert server["prometheus_target_health"] == "unavailable"
    assert server["last_successful_check_at"] is not None


def test_monitoring_marks_stale_snapshots(client, monkeypatch) -> None:
    monkeypatch.setattr("backend.app.modules.monitoring.service.httpx.AsyncClient", _FakeHttpClient)
    monkeypatch.setattr("backend.app.modules.monitoring.service.asyncio.open_connection", _fake_open_connection)
    monkeypatch.setattr("backend.app.modules.monitoring.service.ParamikoSshAdapter.run_command", _fake_systemctl_node_promtail)
    _create_monitoring_integrations(client)
    assert client.post("/api/v1/servers", json=server_payload()).status_code == 201
    assert client.post("/api/v1/monitoring/validate").status_code == 200

    from backend.app.db.session import get_db_session
    from backend.app.main import app
    from backend.app.modules.monitoring.repository import MonitoringSnapshotRepository

    override = app.dependency_overrides[get_db_session]

    async def expire_snapshot() -> None:
        async for session in override():
            server_id = UUID(client.get("/api/v1/servers").json()[0]["id"])
            item = await MonitoringSnapshotRepository(session).get_by_server_id(server_id)
            assert item is not None
            item.stale_after = datetime.now(UTC) - timedelta(minutes=1)
            await session.commit()
            break

    import asyncio

    asyncio.run(expire_snapshot())
    server = client.get("/api/v1/monitoring/overview").json()["servers"][0]

    assert server["monitoring_state"] == "stale"


def test_monitoring_uses_systemctl_fallback_when_ports_are_private(client, monkeypatch) -> None:
    monkeypatch.setattr("backend.app.modules.monitoring.service.httpx.AsyncClient", _FakeHttpClient)
    monkeypatch.setattr("backend.app.modules.monitoring.service.asyncio.open_connection", _fake_open_connection_all_down)
    monkeypatch.setattr("backend.app.modules.monitoring.service.ParamikoSshAdapter.run_command", _fake_systemctl_all_up)
    _create_monitoring_integrations(client)
    assert client.post(
        "/api/v1/servers",
        json=server_payload(hostname="hds-tool", ip_address="192.168.50.15"),
    ).status_code == 201

    assert client.post("/api/v1/monitoring/validate").status_code == 200
    server = client.get("/api/v1/monitoring/overview").json()["servers"][0]

    assert server["monitoring_state"] == "monitored"
    assert server["node_exporter_status"] == "healthy"
    assert server["promtail_status"] == "healthy"
    assert server["cadvisor_status"] == "healthy"


def test_monitoring_uses_docker_ps_fallback_for_cadvisor(client, monkeypatch) -> None:
    monkeypatch.setattr("backend.app.modules.monitoring.service.httpx.AsyncClient", _FakeHttpClient)
    monkeypatch.setattr("backend.app.modules.monitoring.service.asyncio.open_connection", _fake_open_connection_all_down)
    monkeypatch.setattr("backend.app.modules.monitoring.service.ParamikoSshAdapter.run_command", _fake_cadvisor_docker_ps)
    _create_monitoring_integrations(client)
    assert client.post(
        "/api/v1/servers",
        json=server_payload(hostname="hds-tool", ip_address="192.168.50.15"),
    ).status_code == 201

    assert client.post("/api/v1/monitoring/validate").status_code == 200
    server = client.get("/api/v1/monitoring/overview").json()["servers"][0]

    assert server["cadvisor_status"] == "healthy"
    assert server["node_exporter_status"] == "unavailable"
    assert server["promtail_status"] == "unavailable"
