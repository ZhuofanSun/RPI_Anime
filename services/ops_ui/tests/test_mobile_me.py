def test_mobile_me_context_returns_restart_allowlist(client):
    response = client.get("/api/mobile/me/context")

    assert response.status_code == 200
    payload = response.json()
    assert "maintenance" in payload
    assert payload["maintenance"]["restartAll"]["enabled"] is True


def test_mobile_me_restart_returns_scheduled_message(client):
    response = client.post("/api/mobile/me/service-actions/homepage/restart")

    assert response.status_code == 200
    payload = response.json()
    assert payload["scheduled"] is True


def test_mobile_me_restart_rejects_unknown_target(client):
    response = client.post("/api/mobile/me/service-actions/glances/restart")

    assert response.status_code == 404
