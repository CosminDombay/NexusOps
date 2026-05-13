def server_payload(**overrides):
    payload = {
        "hostname": "app-01",
        "ip_address": "10.0.0.10",
        "operating_system": "Ubuntu 24.04 LTS",
        "vmid": "100",
        "environment": "development",
        "tags": ["api", "linux"],
        "ssh_port": 22,
        "ssh_username": "ubuntu",
        "status": "online",
        "provider": "proxmox",
    }
    payload.update(overrides)
    return payload


def test_inventory_crud_flow(client) -> None:
    create_response = client.post("/api/v1/servers", json=server_payload())
    assert create_response.status_code == 201
    created = create_response.json()
    server_id = created["id"]
    assert created["hostname"] == "app-01"

    get_response = client.get(f"/api/v1/servers/{server_id}")
    assert get_response.status_code == 200
    assert get_response.json()["ip_address"] == "10.0.0.10"

    update_response = client.put(
        f"/api/v1/servers/{server_id}",
        json={"environment": "production", "tags": ["api", "critical"]},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["environment"] == "production"
    assert updated["tags"] == ["api", "critical"]

    list_response = client.get("/api/v1/servers", params={"environment": "production"})
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    search_response = client.get("/api/v1/servers", params={"search": "10.0.0"})
    assert search_response.status_code == 200
    assert len(search_response.json()) == 1

    delete_response = client.delete(f"/api/v1/servers/{server_id}")
    assert delete_response.status_code == 204

    missing_response = client.get(f"/api/v1/servers/{server_id}")
    assert missing_response.status_code == 404


def test_inventory_rejects_duplicate_hostname(client) -> None:
    first_response = client.post("/api/v1/servers", json=server_payload())
    assert first_response.status_code == 201

    duplicate_response = client.post(
        "/api/v1/servers",
        json=server_payload(ip_address="10.0.0.11"),
    )
    assert duplicate_response.status_code == 409


def test_inventory_rejects_duplicate_ip_address(client) -> None:
    first_response = client.post("/api/v1/servers", json=server_payload())
    assert first_response.status_code == 201

    duplicate_response = client.post(
        "/api/v1/servers",
        json=server_payload(hostname="app-02"),
    )
    assert duplicate_response.status_code == 409


def test_inventory_validates_ip_address_and_environment(client) -> None:
    bad_ip_response = client.post("/api/v1/servers", json=server_payload(ip_address="not-an-ip"))
    assert bad_ip_response.status_code == 422

    bad_environment_response = client.post(
        "/api/v1/servers",
        json=server_payload(hostname="app-03", ip_address="10.0.0.12", environment="sandbox"),
    )
    assert bad_environment_response.status_code == 422


def test_inventory_filters_by_provider(client) -> None:
    assert client.post("/api/v1/servers", json=server_payload()).status_code == 201
    assert (
        client.post(
            "/api/v1/servers",
            json=server_payload(
                hostname="baremetal-01",
                ip_address="10.0.0.20",
                provider="manual",
                vmid=None,
            ),
        ).status_code
        == 201
    )

    response = client.get("/api/v1/servers", params={"provider": "manual"})
    assert response.status_code == 200
    servers = response.json()
    assert len(servers) == 1
    assert servers[0]["hostname"] == "baremetal-01"


def test_inventory_requires_password_for_password_auth(client) -> None:
    response = client.post(
        "/api/v1/servers",
        json=server_payload(
            hostname="password-host",
            ip_address="10.0.0.30",
            ssh_auth_method="password",
        ),
    )

    assert response.status_code == 422


def test_inventory_accepts_password_auth_without_echoing_secret(client) -> None:
    response = client.post(
        "/api/v1/servers",
        json=server_payload(
            hostname="password-host",
            ip_address="10.0.0.30",
            ssh_auth_method="password",
            ssh_password="secret",
        ),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["ssh_auth_method"] == "password"
    assert "ssh_password" not in payload
