def test_mobile_auth_session_bootstrap_returns_backend_session_contract(anonymous_client):
    response = anonymous_client.post(
        "/api/mobile/auth/session",
        json={"username": "embedded-mobile-user", "password": "embedded-mobile-password"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is True
    assert "token" in payload
    assert "expiresAt" in payload


def test_mobile_auth_session_rejects_bad_credentials(anonymous_client):
    response = anonymous_client.post(
        "/api/mobile/auth/session",
        json={"username": "embedded-mobile-user", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_mobile_protected_routes_require_bearer_token(anonymous_client):
    response = anonymous_client.get("/api/mobile/home/following")

    assert response.status_code == 401
