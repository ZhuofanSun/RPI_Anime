import requests

from anime_ops_ui.services.mobile_media_service import sign_mobile_poster_path


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
