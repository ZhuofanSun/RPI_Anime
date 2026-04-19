import sqlite3
from urllib.parse import parse_qs, urlsplit


def _write_collection_jellyfin_db(data_root, rows):
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
        conn.commit()


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


def test_mobile_detail_supports_real_collection_entries(client):
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
                "JF-SERIES-42",
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
                "JF-EP-42-2",
                "Mayoi Snail",
                None,
                None,
                None,
                None,
                None,
                "/media/collection/Bakemonogatari/Season 1/Bakemonogatari S01E02.mkv",
                "JF-SEASON-42-1",
                "COLLECTION_ROOT",
                2,
                1,
                "JF-SERIES-42",
                "2026-04-19 00:00:00",
                "MediaBrowser.Controller.Entities.TV.Episode",
            ),
        ],
    )

    response = client.get(
        "/api/mobile/items/app_collection_jf_JF-SERIES-42",
        headers={"host": "100.123.232.73:3000"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mappingStatus"] == "mapped"
    assert payload["appItemId"] == "app_collection_jf_JF-SERIES-42"
    assert payload["title"] == "Bakemonogatari"
    assert payload["heroState"] == "playable_primed"
    assert payload["summary"]["freshness"] == "2009"
    assert payload["summary"]["availableEpisodeCount"] == 2
    assert payload["summary"]["seasonLabel"] == "S01"
    assert payload["summary"]["score"] == "8.7"
    assert payload["summary"]["tags"] == ["Supernatural", "Mystery"]
    assert payload["seasons"] == [{"id": "app_collection_jf_JF-SEASON-42-1", "label": "S01", "selected": True}]
    assert payload["episodes"] == [
        {"id": "app_collection_jf_JF-EP-42-1", "label": "E01", "focused": False, "unread": False},
        {"id": "app_collection_jf_JF-EP-42-2", "label": "E02", "focused": True, "unread": False},
    ]
    hero_poster = urlsplit(payload["hero"]["posterUrl"])
    hero_query = parse_qs(hero_poster.query)
    assert hero_poster.netloc == "100.123.232.73:3000"
    assert hero_poster.path == "/api/mobile/media/poster"
    assert hero_query["jellyfinItemId"] == ["JF-SERIES-42"]
    assert payload["overview"] == "A strange story."


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
