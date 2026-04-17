
def test_mobile_auth_session_bootstrap_returns_backend_session_contract(client):
    response = client.post(
        "/api/mobile/auth/session",
        json={"username": "embedded-mobile-user", "password": "embedded-mobile-password"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is True
    assert "token" in payload
    assert "expiresAt" in payload
