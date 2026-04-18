def test_mobile_detail_returns_playable_primed_payload(client):
    response = client.get("/api/mobile/items/app_following_demo")

    assert response.status_code == 200
    payload = response.json()
    assert payload["heroState"] in {"playable_primed", "unavailable"}
    assert payload["appItemId"] == "app_following_demo"
    assert payload["title"] == "灵笼 第一季"
    assert len(payload["recentSeasonal"]) >= 1
    assert payload["recentSeasonal"][0]["appItemId"] == "app_following_demo_5"


def test_mobile_detail_allows_unmapped_payload(client):
    response = client.get("/api/mobile/items/app_following_unmapped")

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
