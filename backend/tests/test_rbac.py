def _token_for(client, username: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": username, "password": "Password123!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_protected_routes_require_authentication(unauthenticated_client) -> None:
    response = unauthenticated_client.get("/api/v1/jobs")

    assert response.status_code == 401


def test_viewer_cannot_access_operator_routes(auth_client) -> None:
    token = _token_for(auth_client, "viewer")

    response = auth_client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_viewer_can_read_inventory_but_cannot_mutate(auth_client) -> None:
    token = _token_for(auth_client, "viewer")
    headers = {"Authorization": f"Bearer {token}"}

    read_response = auth_client.get("/api/v1/servers", headers=headers)
    create_response = auth_client.post(
        "/api/v1/servers",
        headers=headers,
        json={
            "hostname": "viewer-denied",
            "ip_address": "10.10.10.10",
            "operating_system": "Ubuntu",
            "environment": "development",
            "ssh_username": "ubuntu",
        },
    )

    assert read_response.status_code == 200
    assert create_response.status_code == 403


def test_viewer_cannot_access_remote_files(auth_client) -> None:
    token = _token_for(auth_client, "viewer")

    response = auth_client.get(
        "/api/v1/remote-access/hosts/11111111-1111-1111-1111-111111111111/files",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_remote_files_require_authentication(auth_client) -> None:
    response = auth_client.get(
        "/api/v1/remote-access/hosts/11111111-1111-1111-1111-111111111111/files",
    )

    assert response.status_code == 401


def test_operator_can_reach_remote_files_authorization_gate(auth_client) -> None:
    token = _token_for(auth_client, "operator")

    response = auth_client.get(
        "/api/v1/remote-access/hosts/11111111-1111-1111-1111-111111111111/files",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


def test_operator_can_access_operator_routes(auth_client) -> None:
    token = _token_for(auth_client, "operator")

    response = auth_client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200


def test_operator_cannot_access_admin_routes(auth_client) -> None:
    token = _token_for(auth_client, "operator")

    response = auth_client.get(
        "/api/v1/integrations",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_admin_can_access_admin_routes(auth_client) -> None:
    token = _token_for(auth_client, "admin")

    response = auth_client.get(
        "/api/v1/integrations",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200


def test_admin_can_manage_users(auth_client) -> None:
    token = _token_for(auth_client, "admin")

    create_response = auth_client.post(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "username": "new-operator",
            "email": "new-operator@example.com",
            "password": "Password123!",
            "role": "operator",
            "is_active": True,
            "is_superuser": False,
        },
    )

    assert create_response.status_code == 201
    user_id = create_response.json()["id"]

    update_response = auth_client.put(
        f"/api/v1/auth/users/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "viewer", "is_active": False},
    )

    assert update_response.status_code == 200
    assert update_response.json()["role"] == "viewer"
    assert update_response.json()["is_active"] is False


def test_operator_cannot_manage_users(auth_client) -> None:
    token = _token_for(auth_client, "operator")

    response = auth_client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
