import sqlite3

import requests

from anime_ops_ui.services.mobile_media_service import (
    sign_mobile_jellyfin_item_id,
    sign_mobile_poster_path,
    sign_mobile_trickplay_tile_set,
)


def _write_jellyfin_db(data_root, rows):
    db_path = data_root / "appdata" / "jellyfin" / "config" / "data" / "jellyfin.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE BaseItems (
                Id TEXT,
                SeriesId TEXT,
                IndexNumber INTEGER,
                ParentIndexNumber INTEGER,
                Type TEXT
            )
            """
        )
        conn.executemany(
            "INSERT INTO BaseItems (Id, SeriesId, IndexNumber, ParentIndexNumber, Type) VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()


def test_mobile_poster_proxy_forwards_autobangumi_asset(client, monkeypatch):
    captured: list[str] = []

    class _FakeResponse:
        status_code = 200
        content = b"poster-bytes"
        headers = {
            "Content-Type": "image/jpeg",
            "Cache-Control": "public, max-age=600",
            "ETag": '"abc123"',
        }

    def fake_get(url: str, timeout: int):
        captured.append(url)
        return _FakeResponse()

    monkeypatch.setattr(requests, "get", fake_get)

    response = client.get(
        "/api/mobile/media/poster",
        params={
            "path": "posters/ling-long.jpg",
            "sig": sign_mobile_poster_path("posters/ling-long.jpg"),
        },
    )

    assert response.status_code == 200
    assert response.content == b"poster-bytes"
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"] == "public, max-age=600"
    assert response.headers["etag"] == '"abc123"'
    assert captured == ["http://autobangumi:7892/posters/ling-long.jpg"]


def test_mobile_poster_proxy_rejects_invalid_signature(client):
    response = client.get(
        "/api/mobile/media/poster",
        params={
            "path": "posters/ling-long.jpg",
            "sig": "0" * 64,
        },
    )

    assert response.status_code == 403


def test_mobile_poster_proxy_forwards_jellyfin_primary_image(client, monkeypatch):
    captured: list[str] = []

    class _FakeResponse:
        status_code = 200
        content = b"jellyfin-poster"
        headers = {
            "Content-Type": "image/png",
            "Last-Modified": "Fri, 17 Apr 2026 07:12:08 GMT",
        }

    def fake_get(url: str, timeout: int):
        captured.append(url)
        return _FakeResponse()

    monkeypatch.setattr(requests, "get", fake_get)

    response = client.get(
        "/api/mobile/media/poster",
        params={
            "jellyfinItemId": "JF-SERIES-42",
            "sig": sign_mobile_jellyfin_item_id("JF-SERIES-42"),
        },
    )

    assert response.status_code == 200
    assert response.content == b"jellyfin-poster"
    assert response.headers["content-type"] == "image/png"
    assert response.headers["last-modified"] == "Fri, 17 Apr 2026 07:12:08 GMT"
    assert response.headers["cache-control"] == "public, max-age=3600"
    assert captured == ["http://jellyfin:8096/Items/JF-SERIES-42/Images/Primary"]


def test_mobile_poster_proxy_falls_back_to_first_season_image_when_series_image_is_missing(client, monkeypatch):
    data_root = client.app.state.test_paths["data_root"]
    _write_jellyfin_db(
        data_root,
        [
            ("JF-SERIES-42", None, None, None, "MediaBrowser.Controller.Entities.TV.Series"),
            ("JF-SEASON-42-1", "JF-SERIES-42", 1, None, "MediaBrowser.Controller.Entities.TV.Season"),
            ("JF-EP-42-1", "JF-SERIES-42", 1, 1, "MediaBrowser.Controller.Entities.TV.Episode"),
        ],
    )

    captured: list[str] = []

    class _NotFoundResponse:
        status_code = 404
        content = b""
        headers = {"Content-Type": "application/json"}

    class _ImageResponse:
        status_code = 200
        content = b"season-poster"
        headers = {"Content-Type": "image/png"}

    def fake_get(url: str, timeout: int):
        captured.append(url)
        if url.endswith("/Items/JF-SERIES-42/Images/Primary"):
            return _NotFoundResponse()
        if url.endswith("/Items/JF-SEASON-42-1/Images/Primary"):
            return _ImageResponse()
        raise AssertionError(f"unexpected upstream url: {url}")

    monkeypatch.setattr(requests, "get", fake_get)

    response = client.get(
        "/api/mobile/media/poster",
        params={
            "jellyfinItemId": "JF-SERIES-42",
            "sig": sign_mobile_jellyfin_item_id("JF-SERIES-42"),
        },
    )

    assert response.status_code == 200
    assert response.content == b"season-poster"
    assert captured == [
        "http://jellyfin:8096/Items/JF-SERIES-42/Images/Primary",
        "http://jellyfin:8096/Items/JF-SEASON-42-1/Images/Primary",
    ]


def test_mobile_trickplay_tile_proxy_forwards_signed_jellyfin_tile(client, monkeypatch):
    from anime_ops_ui.services import jellyfin_auth_service
    from anime_ops_ui.services import mobile_media_service

    captured: dict = {}

    class _FakeResponse:
        status_code = 200
        content = b"tile-bytes"
        headers = {
            "Content-Type": "image/jpeg",
            "Cache-Control": "public, max-age=7200",
            "ETag": '"tile123"',
        }

    def fake_get(url: str, *, params=None, headers=None, timeout: int):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr(
        mobile_media_service,
        "authenticate_jellyfin_session",
        lambda: jellyfin_auth_service.JellyfinSession(user_id="USER-1", access_token="TOKEN-1"),
    )
    monkeypatch.setattr(requests, "get", fake_get)

    response = client.get(
        "/api/mobile/media/trickplay/tile",
        params={
            "itemId": "JF-EP-42-1",
            "mediaSourceId": "MS-1",
            "width": 320,
            "index": 4,
            "sig": sign_mobile_trickplay_tile_set(item_id="JF-EP-42-1", media_source_id="MS-1", width=320),
        },
    )

    assert response.status_code == 200
    assert response.content == b"tile-bytes"
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"] == "public, max-age=7200"
    assert response.headers["etag"] == '"tile123"'
    assert captured == {
        "url": "http://jellyfin:8096/Videos/JF-EP-42-1/Trickplay/320/4.jpg",
        "params": {"mediaSourceId": "MS-1"},
        "headers": {
            "X-Emby-Authorization": (
                'MediaBrowser Client="NekoYa", Device="NekoYaMobile", '
                'DeviceId="nekoya-mobile-playback", Version="1.0.0"'
            ),
            "X-Emby-Token": "TOKEN-1",
        },
        "timeout": 10,
    }


def test_mobile_trickplay_tile_proxy_rejects_invalid_signature(client):
    response = client.get(
        "/api/mobile/media/trickplay/tile",
        params={
            "itemId": "JF-EP-42-1",
            "mediaSourceId": "MS-1",
            "width": 320,
            "index": 4,
            "sig": "0" * 64,
        },
    )

    assert response.status_code == 403
