def test_mobile_me_context_returns_service_health(client):
    response = client.get("/api/mobile/me/context")

    assert response.status_code == 200
    payload = response.json()
    assert "serviceHealth" in payload
    assert "maintenance" not in payload
    assert any(item["target"] == "jellyfin" for item in payload["serviceHealth"])
