from anime_ops_ui.domain.mobile_models import HomeFollowingItem


def test_mobile_home_following_returns_card_contract(client, monkeypatch):
    from anime_ops_ui.services import mobile_home_service

    monkeypatch.setattr(
        mobile_home_service,
        "build_following_items",
        lambda: [
            HomeFollowingItem(
                appItemId="app_following_ab_42",
                title="灵笼 第一季",
                posterUrl="https://example.com/poster.jpg",
                unread=True,
                mappingStatus="mapped",
                jellyfinSeriesId="series_123",
                availabilityState="mapped_playable",
            )
        ],
    )
    response = client.get("/api/mobile/home/following")

    assert response.status_code == 200
    payload = response.json()
    assert payload["updatedAt"] != "2099-01-01T00:00:00Z"
    first = payload["items"][0]
    assert {"appItemId", "title", "posterUrl", "unread", "mappingStatus", "availabilityState"} <= set(first)
    assert first["appItemId"] == "app_following_ab_42"


def test_mobile_home_favorites_returns_collection_grid_contract(client):
    response = client.get("/api/mobile/home/favorites")

    assert response.status_code == 200
    payload = response.json()
    assert payload["updatedAt"] != "2099-01-01T00:00:00Z"
    first = payload["items"][0]
    assert {"appItemId", "title", "posterUrl", "unread", "mappingStatus", "availabilityState"} <= set(first)
    assert first["appItemId"].startswith("app_collection_")
