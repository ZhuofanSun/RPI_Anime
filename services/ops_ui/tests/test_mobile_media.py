import sqlite3

import requests

from anime_ops_ui.services.mobile_media_service import sign_mobile_jellyfin_item_id, sign_mobile_poster_path


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
