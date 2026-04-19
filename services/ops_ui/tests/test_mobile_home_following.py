from urllib.parse import parse_qs, urlsplit

from anime_ops_ui.domain.mobile_models import HomeFollowingItem


def test_mobile_home_following_returns_card_contract(client, monkeypatch):
    from anime_ops_ui.services import mobile_home_service

    monkeypatch.setattr(
        mobile_home_service,
        "build_following_items",
        lambda public_host=None, public_base_url=None: [
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


def test_mobile_home_following_uses_request_host_for_generated_urls(client, monkeypatch):
    from anime_ops_ui.services import mobile_seasonal_service

    captured_hosts: list[str] = []

    def fake_snapshot(
        *,
        anime_data_root,
        base_host,
        autobangumi_port,
        jellyfin_port,
        autobangumi_base_url,
        autobangumi_username,
        autobangumi_password,
        state_root,
        now,
        events,
        visible_limit,
    ):
        captured_hosts.append(base_host)
        return {
            "weekly_schedule": {
                "days": [
                    {
                        "label": "周六",
                        "items": [
                            {
                                "id": 42,
                                "title": "灵笼 第一季",
                                "poster_url": f"http://{base_host}:7892/posters/ling-long.jpg",
                                "jellyfin_url": f"http://{base_host}:8096/web/#/details?id=series_123",
                                "is_library_ready": True,
                                "detail": {},
                            }
                        ],
                        "hidden_items": [],
                    }
                ]
            }
        }

    monkeypatch.setenv("HOMEPAGE_BASE_HOST", "sunzhuofan.local")
    monkeypatch.setattr(mobile_seasonal_service, "_SNAPSHOT_CACHE", None)
    monkeypatch.setattr(mobile_seasonal_service, "build_phase4_schedule_snapshot", fake_snapshot)

    response = client.get("/api/mobile/home/following", headers={"host": "100.123.232.73:3000"})

    assert response.status_code == 200
    payload = response.json()
    assert captured_hosts == ["100.123.232.73"]
    poster = urlsplit(payload["items"][0]["posterUrl"])
    query = parse_qs(poster.query)
    assert poster.scheme == "http"
    assert poster.netloc == "100.123.232.73:3000"
    assert poster.path == "/api/mobile/media/poster"
    assert query["path"] == ["posters/ling-long.jpg"]
    assert len(query["sig"][0]) == 64


def test_mobile_home_following_cache_varies_by_request_host(client, monkeypatch):
    from anime_ops_ui.services import mobile_seasonal_service

    captured_hosts: list[str] = []

    def fake_snapshot(
        *,
        anime_data_root,
        base_host,
        autobangumi_port,
        jellyfin_port,
        autobangumi_base_url,
        autobangumi_username,
        autobangumi_password,
        state_root,
        now,
        events,
        visible_limit,
    ):
        captured_hosts.append(base_host)
        return {
            "weekly_schedule": {
                "days": [
                    {
                        "label": "周六",
                        "items": [
                            {
                                "id": 42,
                                "title": "灵笼 第一季",
                                "poster_url": f"http://{base_host}:7892/posters/ling-long.jpg",
                                "jellyfin_url": f"http://{base_host}:8096/web/#/details?id=series_123",
                                "is_library_ready": True,
                                "detail": {},
                            }
                        ],
                        "hidden_items": [],
                    }
                ]
            }
        }

    monkeypatch.setenv("HOMEPAGE_BASE_HOST", "sunzhuofan.local")
    monkeypatch.setattr(mobile_seasonal_service, "_SNAPSHOT_CACHE", None)
    monkeypatch.setattr(mobile_seasonal_service, "build_phase4_schedule_snapshot", fake_snapshot)

    first = client.get("/api/mobile/home/following", headers={"host": "100.123.232.73:3000"})
    second = client.get("/api/mobile/home/following", headers={"host": "100.88.77.66:3000"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert captured_hosts == ["100.123.232.73", "100.88.77.66"]
    poster = urlsplit(second.json()["items"][0]["posterUrl"])
    query = parse_qs(poster.query)
    assert poster.netloc == "100.88.77.66:3000"
    assert poster.path == "/api/mobile/media/poster"
    assert query["path"] == ["posters/ling-long.jpg"]
