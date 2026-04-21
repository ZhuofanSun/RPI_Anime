import sqlite3
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from anime_ops_ui.domain.mobile_models import HomeFollowingItem


def _write_collection_jellyfin_db(data_root, rows, *, user_rows=None):
    db_path = data_root / "appdata" / "jellyfin" / "config" / "data" / "jellyfin.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE BaseItems (
                Id TEXT,
                Name TEXT,
                OriginalTitle TEXT,
                Overview TEXT,
                CommunityRating REAL,
                PremiereDate TEXT,
                Tags TEXT,
                Path TEXT,
                ParentId TEXT,
                TopParentId TEXT,
                IndexNumber INTEGER,
                ParentIndexNumber INTEGER,
                SeriesId TEXT,
                DateCreated TEXT,
                Type TEXT
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO BaseItems (
                Id, Name, OriginalTitle, Overview, CommunityRating, PremiereDate, Tags, Path,
                ParentId, TopParentId, IndexNumber, ParentIndexNumber, SeriesId, DateCreated, Type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        if user_rows is not None:
            conn.execute(
                """
                CREATE TABLE UserDatas (
                    ItemId TEXT,
                    UserId TEXT,
                    Played INTEGER
                )
                """
            )
            conn.executemany(
                """
                INSERT INTO UserDatas (
                    ItemId, UserId, Played
                ) VALUES (?, ?, ?)
                """,
                user_rows,
            )
        conn.commit()


def _series_mapping_rows(*, series_id: str, title: str) -> list[tuple]:
    return [
        (
            series_id,
            title,
            title,
            None,
            None,
            None,
            None,
            f"/media/seasonal/{title}",
            None,
            None,
            None,
            None,
            None,
            "2026-04-19 00:00:00",
            "MediaBrowser.Controller.Entities.TV.Series",
        ),
        (
            f"{series_id}-season-1",
            "Season 1",
            None,
            None,
            None,
            None,
            None,
            f"/media/seasonal/{title}/Season 1",
            series_id,
            None,
            1,
            None,
            series_id,
            "2026-04-19 00:00:00",
            "MediaBrowser.Controller.Entities.TV.Season",
        ),
        (
            f"{series_id}-ep-1",
            "Episode 1",
            None,
            None,
            None,
            None,
            None,
            f"/media/seasonal/{title}/Season 1/{title} S01E01.mkv",
            f"{series_id}-season-1",
            None,
            1,
            1,
            series_id,
            "2026-04-19 00:00:00",
            "MediaBrowser.Controller.Entities.TV.Episode",
        ),
        (
            f"{series_id}-ep-2",
            "Episode 2",
            None,
            None,
            None,
            None,
            None,
            f"/media/seasonal/{title}/Season 1/{title} S01E02.mkv",
            f"{series_id}-season-1",
            None,
            2,
            1,
            series_id,
            "2026-04-19 00:00:00",
            "MediaBrowser.Controller.Entities.TV.Episode",
        ),
    ]


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


def test_mobile_home_favorites_returns_real_collection_grid_contract(client):
    data_root = client.app.state.test_paths["data_root"]
    _write_collection_jellyfin_db(
        data_root,
        [
            (
                "COLLECTION_ROOT",
                "collection",
                None,
                None,
                None,
                None,
                None,
                "/media/collection",
                None,
                None,
                None,
                None,
                None,
                "2026-04-19 00:00:00",
                "MediaBrowser.Controller.Entities.Folder",
            ),
            (
                "JF-SERIES-42",
                "Bakemonogatari",
                "Bakemonogatari",
                "A strange story.",
                8.7,
                "2009-07-03 00:00:00",
                "Supernatural|Mystery",
                "/media/collection/Bakemonogatari",
                "COLLECTION_ROOT",
                "COLLECTION_ROOT",
                None,
                None,
                None,
                "2026-04-19 00:00:00",
                "MediaBrowser.Controller.Entities.TV.Series",
            ),
            (
                "JF-SEASON-42-1",
                "Season 1",
                None,
                None,
                None,
                None,
                None,
                "/media/collection/Bakemonogatari/Season 1",
                "JF-SERIES-42",
                "COLLECTION_ROOT",
                1,
                None,
                "JF_SERIES_42",
                "2026-04-19 00:00:00",
                "MediaBrowser.Controller.Entities.TV.Season",
            ),
            (
                "JF-EP-42-1",
                "Hitagi Crab",
                None,
                None,
                None,
                None,
                None,
                "/media/collection/Bakemonogatari/Season 1/Bakemonogatari S01E01.mkv",
                "JF-SEASON-42-1",
                "COLLECTION_ROOT",
                1,
                1,
                "JF-SERIES-42",
                "2026-04-19 00:00:00",
                "MediaBrowser.Controller.Entities.TV.Episode",
            ),
            (
                "JF-SERIES-OUTSIDE",
                "Seasonal Title",
                "Seasonal Title",
                None,
                None,
                None,
                None,
                "/media/seasonal/Seasonal Title",
                None,
                None,
                None,
                None,
                None,
                "2026-04-19 00:00:00",
                "MediaBrowser.Controller.Entities.TV.Series",
            ),
        ],
    )

    response = client.get("/api/mobile/home/favorites", headers={"host": "100.123.232.73:3000"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["updatedAt"] != "2099-01-01T00:00:00Z"
    assert len(payload["items"]) == 1
    first = payload["items"][0]
    assert {"appItemId", "title", "posterUrl", "unread", "mappingStatus", "availabilityState"} <= set(first)
    poster = urlsplit(first["posterUrl"])
    query = parse_qs(poster.query)
    assert first["appItemId"] == "app_collection_jf_JF-SERIES-42"
    assert first["title"] == "Bakemonogatari"
    assert first["jellyfinSeriesId"] == "JF-SERIES-42"
    assert first["premiereYear"] == "2009"
    assert first["mappingStatus"] == "mapped"
    assert first["availabilityState"] == "mapped_playable"
    assert poster.netloc == "100.123.232.73:3000"
    assert poster.path == "/api/mobile/media/poster"
    assert query["jellyfinItemId"] == ["JF-SERIES-42"]
    assert len(query["sig"][0]) == 64


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


def test_mobile_home_following_requires_real_jellyfin_mapping_for_mapped_states(client, monkeypatch):
    from anime_ops_ui.services import mobile_seasonal_service

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
                                "jellyfin_url": None,
                                "is_library_ready": True,
                                "detail": {},
                            }
                        ],
                        "hidden_items": [],
                    }
                ]
            }
        }

    monkeypatch.setattr(mobile_seasonal_service, "_SNAPSHOT_CACHE", None)
    monkeypatch.setattr(mobile_seasonal_service, "build_phase4_schedule_snapshot", fake_snapshot)

    response = client.get("/api/mobile/home/following", headers={"host": "100.123.232.73:3000"})

    assert response.status_code == 200
    payload = response.json()
    first = payload["items"][0]
    assert first["mappingStatus"] == "unmapped"
    assert first["availabilityState"] == "subscription_only"
    assert first["unread"] is False


def test_mobile_home_following_uses_jellyfin_inventory_for_playable_state(client, monkeypatch):
    from anime_ops_ui.services import mobile_seasonal_service

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
                                "jellyfin_series_id": "series_123",
                                "has_playable_episodes": True,
                                "is_library_ready": False,
                                "detail": {},
                            }
                        ],
                        "hidden_items": [],
                    }
                ]
            }
        }

    monkeypatch.setattr(mobile_seasonal_service, "_SNAPSHOT_CACHE", None)
    monkeypatch.setattr(mobile_seasonal_service, "build_phase4_schedule_snapshot", fake_snapshot)

    response = client.get("/api/mobile/home/following", headers={"host": "100.123.232.73:3000"})

    assert response.status_code == 200
    payload = response.json()
    first = payload["items"][0]
    assert first["mappingStatus"] == "mapped"
    assert first["availabilityState"] == "mapped_playable"
    assert first["unread"] is False


def test_mobile_home_following_uses_jellyfin_inventory_for_unread_state(client, monkeypatch):
    from anime_ops_ui.services import mobile_seasonal_service

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
                                "jellyfin_series_id": "series_123",
                                "has_playable_episodes": True,
                                "has_unwatched_episodes": True,
                                "is_library_ready": True,
                                "detail": {},
                            }
                        ],
                        "hidden_items": [],
                    }
                ]
            }
        }

    monkeypatch.setattr(mobile_seasonal_service, "_SNAPSHOT_CACHE", None)
    monkeypatch.setattr(mobile_seasonal_service, "build_phase4_schedule_snapshot", fake_snapshot)

    response = client.get("/api/mobile/home/following", headers={"host": "100.123.232.73:3000"})

    assert response.status_code == 200
    payload = response.json()
    first = payload["items"][0]
    assert first["mappingStatus"] == "mapped"
    assert first["availabilityState"] == "mapped_playable"
    assert first["unread"] is True


def test_series_mapping_index_marks_series_unread_from_jellyfin_watch_state(client, monkeypatch):
    from anime_ops_ui.services import jellyfin_watch_state_service, series_mapping_service

    data_root = client.app.state.test_paths["data_root"]
    state_root = Path(client.app.state.test_paths["state_root"])
    playback_user_id = "1D196118-259B-4D30-8EE6-CF3D5CE1B35F"
    _write_collection_jellyfin_db(
        data_root,
        _series_mapping_rows(series_id="JF-SERIES-99", title="Ling Cage"),
        user_rows=[
            ("JF-SERIES-99-ep-2", playback_user_id, 1),
        ],
    )
    monkeypatch.setattr(jellyfin_watch_state_service, "_playback_user_cache", None)
    monkeypatch.setattr(
        jellyfin_watch_state_service,
        "resolve_playback_user_id",
        lambda: "1d196118259b4d308ee6cf3d5ce1b35f",
    )

    index = series_mapping_service.build_series_mapping_index(
        anime_data_root=data_root,
        bangumi_items=[
            {
                "id": 42,
                "title": "Ling Cage",
                "title_raw": "Ling Cage",
                "official_title": "Ling Cage",
            }
        ],
        state_root=state_root,
    )

    assert index[42]["jellyfinSeriesId"] == "JF-SERIES-99"
    assert index[42]["availableEpisodeCount"] == 2
    assert index[42]["hasPlayableEpisodes"] is True
    assert index[42]["hasUnwatchedEpisodes"] is True
