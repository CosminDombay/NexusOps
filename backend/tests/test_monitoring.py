from backend.tests.test_inventory import server_payload


class _FakeResponse:
    def __init__(self, payload=None) -> None:
        self.payload = payload or {}

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self.payload


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs) -> None:
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def get(self, url, **kwargs):
        if url.endswith("/-/healthy"):
            return _FakeResponse()
        return _FakeResponse({"data": {"result": [{"value": [0, "42.5"]}]}})


def test_monitoring_uses_prometheus_integration(client, monkeypatch) -> None:
    monkeypatch.setattr("backend.app.modules.monitoring.service.httpx.AsyncClient", _FakeAsyncClient)

    create_integration_response = client.post(
        "/api/v1/integrations",
        json={
            "name": "Metrics provider",
            "type": "monitoring",
            "provider_type": "prometheus",
            "enabled": True,
            "config": {"url": "http://prometheus.internal:9090", "verify_ssl": False, "timeout_seconds": 7},
            "credential_refs": {},
        },
    )
    assert create_integration_response.status_code == 201
    assert client.post("/api/v1/servers", json=server_payload()).status_code == 201

    response = client.get("/api/v1/monitoring/overview")

    assert response.status_code == 200
    payload = response.json()
    prometheus = next(provider for provider in payload["providers"] if provider["provider_type"] == "prometheus")
    assert prometheus["configured"] is True
    assert prometheus["reachable"] is True
    assert prometheus["url"] == "http://prometheus.internal:9090"
    assert payload["servers"][0]["cpu_usage_percent"] == 42.5
    assert payload["servers"][0]["prometheus_url"].startswith("http://prometheus.internal:9090/graph")


def test_monitoring_missing_prometheus_returns_partial_data(client) -> None:
    assert client.post("/api/v1/servers", json=server_payload()).status_code == 201

    response = client.get("/api/v1/monitoring/overview")

    assert response.status_code == 200
    payload = response.json()
    prometheus = next(provider for provider in payload["providers"] if provider["provider_type"] == "prometheus")
    assert prometheus["configured"] is False
    assert prometheus["reachable"] is False
    assert payload["servers"][0]["cpu_usage_percent"] is None
    assert payload["servers"][0]["metrics_error"] == "Prometheus integration is not configured or is disabled"
