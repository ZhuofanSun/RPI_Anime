def test_mobile_detail_returns_playable_primed_payload(client):
    response = client.get("/api/mobile/items/app_following_demo")

    assert response.status_code == 200
    payload = response.json()
    assert payload["heroState"] in {"playable_primed", "unavailable"}
    assert payload["appItemId"] == "app_following_demo"


def test_mobile_detail_allows_unmapped_payload(client):
    response = client.get("/api/mobile/items/app_following_unmapped")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mappingStatus"] == "unmapped"
    assert payload["heroState"] == "unavailable"
