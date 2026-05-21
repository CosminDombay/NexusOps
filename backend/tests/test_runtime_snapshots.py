from backend.tests.test_inventory import server_payload


def test_inventory_list_reads_persisted_runtime_snapshot(client) -> None:
    create_response = client.post("/api/v1/servers", json=server_payload())
    assert create_response.status_code == 201

    list_response = client.get("/api/v1/servers")

    assert list_response.status_code == 200
    runtime_state = list_response.json()[0]["runtime_state"]
    assert runtime_state["provider_state"] == "unknown"
    assert runtime_state["eligibility"]["can_sync_provider"] is True
    assert runtime_state["last_checked_at"] is not None
    assert runtime_state["stale_after"] is not None


def test_runtime_snapshot_inventory_refresh_endpoint(client) -> None:
    assert client.post("/api/v1/servers", json=server_payload()).status_code == 201

    response = client.post("/api/v1/runtime-state/refresh/inventory")

    assert response.status_code == 200
    statuses = response.json()
    inventory_status = next(status for status in statuses if status["scope"] == "inventory")
    assert inventory_status["status"] == "success"
    assert inventory_status["metadata_json"]["node_count"] == 1


def test_monitoring_overview_uses_snapshots_without_live_provider_checks(client, monkeypatch) -> None:
    def fail_live_monitoring(*args, **kwargs):  # pragma: no cover - only executed on regression
        raise AssertionError("monitoring overview must not open live HTTP clients")

    monkeypatch.setattr("backend.app.modules.monitoring.service.httpx.AsyncClient", fail_live_monitoring)
    assert client.post("/api/v1/servers", json=server_payload()).status_code == 201

    response = client.get("/api/v1/monitoring/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_servers"] == 1
    assert payload["servers"][0]["cpu_usage_percent"] is None
    assert payload["servers"][0]["monitoring_state"] == "unknown"
