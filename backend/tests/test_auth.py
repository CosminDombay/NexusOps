from backend.app.modules.auth.security.hashing import hash_password, verify_password


def test_password_hashing_never_returns_plaintext() -> None:
    password_hash = hash_password("Password123!")

    assert password_hash != "Password123!"
    assert verify_password("Password123!", password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_login_success_returns_tokens_and_user(auth_client) -> None:
    response = auth_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin@example.com", "password": "Password123!"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["user"]["username"] == "admin"
    assert payload["user"]["role"] == "admin"
    assert "password_hash" not in payload["user"]


def test_login_failure_rejects_bad_password(auth_client) -> None:
    response = auth_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_me_validates_access_token(auth_client) -> None:
    login_response = auth_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "operator", "password": "Password123!"},
    )
    token = login_response.json()["access_token"]

    response = auth_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["username"] == "operator"


def test_refresh_token_flow(auth_client) -> None:
    login_response = auth_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "viewer", "password": "Password123!"},
    )

    response = auth_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login_response.json()["refresh_token"]},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.json()["user"]["role"] == "viewer"


def test_logout_revokes_existing_refresh_token(auth_client) -> None:
    login_response = auth_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "viewer", "password": "Password123!"},
    )
    payload = login_response.json()

    logout_response = auth_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )
    refresh_response = auth_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": payload["refresh_token"]},
    )

    assert logout_response.status_code == 204
    assert refresh_response.status_code == 401


def test_password_reset_revokes_existing_access_token(auth_client) -> None:
    login_response = auth_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "viewer", "password": "Password123!"},
    )
    viewer_payload = login_response.json()

    admin_login = auth_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin", "password": "Password123!"},
    )
    users_response = auth_client.get(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {admin_login.json()['access_token']}"},
    )
    viewer = next(user for user in users_response.json() if user["username"] == "viewer")
    reset_response = auth_client.post(
        f"/api/v1/auth/users/{viewer['id']}/reset-password",
        headers={"Authorization": f"Bearer {admin_login.json()['access_token']}"},
        json={"password": "NewPassword123!"},
    )
    me_response = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {viewer_payload['access_token']}"},
    )

    assert reset_response.status_code == 200
    assert me_response.status_code == 401
