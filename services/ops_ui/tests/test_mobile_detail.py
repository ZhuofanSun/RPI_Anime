from urllib.parse import parse_qs, urlsplit


def test_mobile_detail_returns_playable_primed_payload(client, monkeypatch):
    from anime_ops_ui.services import mobile_detail_service

    monkeypatch.setattr(
        mobile_detail_service,
        "get_seasonal_item",
        lambda app_item_id, public_host=None, public_base_url=None: {
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
        lambda exclude_app_item_id=None, limit=6, public_host=None, public_base_url=None: [
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
        lambda app_item_id, public_host=None, public_base_url=None: {
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
        lambda exclude_app_item_id=None, limit=6, public_host=None, public_base_url=None: [
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


def test_mobile_detail_uses_request_host_for_seasonal_payload(client, monkeypatch):
    from anime_ops_ui.services import mobile_detail_service

    captured: dict[str, str | None] = {}

    def fake_get_seasonal_item(app_item_id, public_host=None, public_base_url=None):
        captured["item_host"] = public_host
        return {
            "appItemId": "app_following_ab_42",
            "title": "灵笼 第一季",
            "posterUrl": f"http://{public_host}:7892/posters/ling-long.jpg",
            "mappingStatus": "mapped",
            "availabilityState": "mapped_playable",
            "isLibraryReady": True,
        }

    def fake_build_recent_seasonal(exclude_app_item_id=None, limit=6, public_host=None, public_base_url=None):
        captured["recent_host"] = public_host
        return [
            {
                "appItemId": "app_following_ab_7",
                "title": "时光代理人",
                "posterUrl": f"http://{public_host}:7892/posters/recent.jpg",
                "subtitle": "更新至第 12 集",
            }
        ]

    monkeypatch.setattr(mobile_detail_service, "get_seasonal_item", fake_get_seasonal_item)
    monkeypatch.setattr(mobile_detail_service, "build_recent_seasonal", fake_build_recent_seasonal)

    response = client.get("/api/mobile/items/app_following_ab_42", headers={"host": "100.123.232.73:3000"})

    assert response.status_code == 200
    payload = response.json()
    assert captured == {"item_host": "100.123.232.73", "recent_host": "100.123.232.73"}
    hero_poster = urlsplit(payload["hero"]["posterUrl"])
    hero_query = parse_qs(hero_poster.query)
    recent_poster = urlsplit(payload["recentSeasonal"][0]["posterUrl"])
    recent_query = parse_qs(recent_poster.query)
    assert hero_poster.netloc == "100.123.232.73:3000"
    assert hero_poster.path == "/api/mobile/media/poster"
    assert hero_query["path"] == ["posters/ling-long.jpg"]
    assert recent_poster.netloc == "100.123.232.73:3000"
    assert recent_poster.path == "/api/mobile/media/poster"
    assert recent_query["path"] == ["posters/recent.jpg"]
