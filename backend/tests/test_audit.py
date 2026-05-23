from backend.tests.test_inventory import server_payload


def test_auth_login_persists_audit_event(auth_client) -> None:
    response = auth_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin", "password": "Password123!"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]

    audit_response = auth_client.get(
        "/api/v1/audit-events",
        params={"event_type": "auth.login"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert audit_response.status_code == 200
    events = audit_response.json()
    assert events
    assert events[0]["event_type"] == "auth.login"
    assert events[0]["result"] == "success"
    assert events[0]["actor_username"] == "admin"


def test_monitoring_validation_persists_attempt_and_audit_event(client, monkeypatch) -> None:
    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

    class _FakeHttpClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

        async def get(self, url, **kwargs):
            return _FakeResponse()

    class _FakeWriter:
        def close(self) -> None:
            return None

        async def wait_closed(self) -> None:
            return None

    async def fake_open_connection(host, port):
        if port == 9100:
            return object(), _FakeWriter()
        raise OSError("connection refused")

    monkeypatch.setattr("backend.app.modules.monitoring.service.httpx.AsyncClient", _FakeHttpClient)
    monkeypatch.setattr("backend.app.modules.monitoring.service.asyncio.open_connection", fake_open_connection)

    assert client.post(
        "/api/v1/integrations",
        json={
            "name": "Prometheus",
            "type": "monitoring",
            "provider_type": "prometheus",
            "enabled": True,
            "config": {"url": "http://prometheus.internal:9090"},
            "credential_refs": {},
        },
    ).status_code == 201
    create_response = client.post("/api/v1/servers", json=server_payload())
    assert create_response.status_code == 201
    server_id = create_response.json()["id"]

    validate_response = client.post("/api/v1/monitoring/validate")
    assert validate_response.status_code == 200

    attempts_response = client.get(f"/api/v1/monitoring/servers/{server_id}/validation-attempts")
    assert attempts_response.status_code == 200
    attempts = attempts_response.json()
    assert attempts
    assert attempts[0]["server_id"] == server_id
    assert attempts[0]["validation_method"] == "tcp_http_ssh"
    assert attempts[0]["component_results"]["node_exporter"]["status"] == "healthy"
    assert attempts[0]["component_results"]["promtail"]["failure_reason"] in {
        "tcp_unreachable",
        "ssh_auth_failed",
    }

    audit_response = client.get("/api/v1/audit-events", params={"event_type": "monitoring.validation"})
    assert audit_response.status_code == 200
    events = audit_response.json()
    assert events
    assert events[0]["target_id"] == server_id
    assert events[0]["metadata_json"]["validation_method"] == "tcp_http_ssh"
