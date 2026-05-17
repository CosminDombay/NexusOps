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
