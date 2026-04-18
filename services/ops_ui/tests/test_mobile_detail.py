def test_mobile_detail_returns_playable_primed_payload(client, monkeypatch):
    from anime_ops_ui.services import mobile_detail_service

    monkeypatch.setattr(
        mobile_detail_service,
        "get_seasonal_item",
        lambda app_item_id: {
            "appItemId": "app_following_ab_42",
            "title": "灵笼 第一季",
            "posterUrl": "https://example.com/poster.jpg",
            "mappingStatus": "mapped",
            "availabilityState": "mapped_playable",
            "isLibraryReady": True,
        },
    )
    monkeypatch.setattr(
        mobile_detail_service,
        "build_recent_seasonal",
        lambda exclude_app_item_id=None, limit=6: [
            {
                "appItemId": "app_following_ab_7",
                "title": "时光代理人",
                "posterUrl": "https://example.com/recent.jpg",
                "subtitle": "更新至第 12 集",
            }
        ],
    )

    response = client.get("/api/mobile/items/app_following_ab_42")

    assert response.status_code == 200
    payload = response.json()
    assert payload["heroState"] in {"playable_primed", "unavailable"}
    assert payload["appItemId"] == "app_following_ab_42"
    assert payload["title"] == "灵笼 第一季"
    assert len(payload["recentSeasonal"]) >= 1
    assert payload["recentSeasonal"][0]["appItemId"] == "app_following_ab_7"


def test_mobile_detail_allows_unmapped_payload(client, monkeypatch):
    from anime_ops_ui.services import mobile_detail_service

    monkeypatch.setattr(
        mobile_detail_service,
        "get_seasonal_item",
        lambda app_item_id: {
            "appItemId": "app_following_ab_999",
            "title": "天官赐福",
            "posterUrl": "https://example.com/poster.jpg",
            "mappingStatus": "unmapped",
            "availabilityState": "subscription_only",
            "isLibraryReady": False,
        },
    )
    monkeypatch.setattr(
        mobile_detail_service,
        "build_recent_seasonal",
        lambda exclude_app_item_id=None, limit=6: [
            {
                "appItemId": "app_following_ab_7",
                "title": "时光代理人",
                "posterUrl": "https://example.com/recent.jpg",
                "subtitle": "更新至第 12 集",
            }
        ],
    )

    response = client.get("/api/mobile/items/app_following_ab_999")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mappingStatus"] == "unmapped"
    assert payload["heroState"] == "unavailable"
    assert len(payload["recentSeasonal"]) >= 1


def test_mobile_detail_supports_collection_entries(client):
    response = client.get("/api/mobile/items/app_collection_demo_1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mappingStatus"] == "mapped"
    assert payload["title"] == "罗小黑战记"
