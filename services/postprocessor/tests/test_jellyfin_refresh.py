from pathlib import Path

from anime_postprocessor.jellyfin_refresh import (
    collect_series_updates,
    derive_series_refresh_path,
    post_series_updates,
)


def test_derive_series_refresh_path_prefers_series_directory():
    path = Path("/library/Demo Show/Season 1/Demo Show S01E01.mp4")

    assert derive_series_refresh_path(path) == Path("/library/Demo Show")


def test_collect_series_updates_deduplicates_paths_using_latest_update_type():
    updates = collect_series_updates(
        [
            {
                "jellyfin_refresh_path": "/library/Demo Show",
                "jellyfin_refresh_update_type": "Created",
            },
            {
                "jellyfin_refresh_path": "/library/Demo Show",
                "jellyfin_refresh_update_type": "Modified",
            },
            {
                "jellyfin_refresh_path": "/library/Another Show",
                "jellyfin_refresh_update_type": "Modified",
            },
        ]
    )

    assert updates == [
        {
            "Path": "/library/Demo Show",
            "UpdateType": "Modified",
        },
        {
            "Path": "/library/Another Show",
            "UpdateType": "Modified",
        },
    ]


def test_post_series_updates_authenticates_and_notifies_jellyfin(monkeypatch):
    calls: list[dict] = []

    class _Response:
        def __init__(self, status_code: int, payload: dict | None = None) -> None:
            self.status_code = status_code
            self._payload = payload or {}

        def json(self) -> dict:
            return self._payload

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        if url.endswith("/Users/AuthenticateByName"):
            return _Response(
                200,
                {
                    "AccessToken": "demo-token",
                    "User": {"Id": "demo-user"},
                },
            )
        if url.endswith("/Library/Series/Updated"):
            return _Response(204)
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("anime_postprocessor.jellyfin_refresh.requests.post", fake_post)

    summary = post_series_updates(
        [
            {
                "Path": "/library/Demo Show",
                "UpdateType": "Modified",
            }
        ]
    )

    assert len(calls) == 2
    assert calls[0]["url"] == "http://jellyfin:8096/Users/AuthenticateByName"
    assert calls[1]["url"] == "http://jellyfin:8096/Library/Series/Updated"
    assert calls[1]["json"] == {
        "Updates": [
            {
                "Path": "/library/Demo Show",
                "UpdateType": "Modified",
            }
        ]
    }
    assert summary == {
        "endpoint": "/Library/Series/Updated",
        "path_count": 1,
        "update_types": ["Modified"],
        "paths": ["/library/Demo Show"],
    }
