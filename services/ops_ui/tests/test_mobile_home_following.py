def test_mobile_home_following_returns_card_contract(client):
    response = client.get("/api/mobile/home/following")

    assert response.status_code == 200
    payload = response.json()
    assert payload["updatedAt"] == "2099-01-01T00:00:00Z"
    first = payload["items"][0]
    assert {"appItemId", "title", "posterUrl", "unread", "mappingStatus", "availabilityState"} <= set(first)


def test_mobile_home_favorites_returns_collection_grid_contract(client):
    response = client.get("/api/mobile/home/favorites")

    assert response.status_code == 200
    payload = response.json()
    assert payload["updatedAt"] == "2099-01-01T00:00:00Z"
    first = payload["items"][0]
    assert {"appItemId", "title", "posterUrl", "unread", "mappingStatus", "availabilityState"} <= set(first)
    assert first["appItemId"].startswith("app_collection_")
