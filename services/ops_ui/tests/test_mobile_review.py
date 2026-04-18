import os
from pathlib import Path

from anime_ops_ui import main as main_module


def _create_review_file(review_root: Path, relative_path: str, *, mtime: int) -> Path:
    path = review_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"demo-media")
    os.utime(path, (mtime, mtime))
    return path


def _review_item_id(relative_path: str) -> str:
    return relative_path.replace("/", "__")


def test_mobile_review_list_returns_lightweight_queue_contract(client, tmp_path, monkeypatch):
    review_root = tmp_path / "manual_review"
    newer_relative = "unparsed/My Series/Season 1/My Series S01E02.mkv"
    older_relative = "duplicates/Another Series/Season 1/Another Series S01E01.mkv"
    _create_review_file(review_root, older_relative, mtime=1_713_312_000)
    _create_review_file(review_root, newer_relative, mtime=1_713_398_400)
    monkeypatch.setattr(main_module, "_manual_review_root", lambda: review_root)

    response = client.get("/api/mobile/review", headers={"Accept-Language": "en"})

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"items", "updatedAt"}
    assert [item["reviewItemId"] for item in payload["items"]] == [
        _review_item_id(newer_relative),
        _review_item_id(older_relative),
    ]
    first = payload["items"][0]
    assert set(first) == {
        "reviewItemId",
        "title",
        "summary",
        "failureReason",
        "state",
        "queuedAt",
    }
    assert first["title"] == "My Series"
    assert "Episode 2" in first["summary"]
    assert "My Series S01E02.mkv" in first["summary"]
    assert first["failureReason"] == "Could not reliably parse title or season/episode"
    assert first["state"] == "pending"


def test_mobile_review_detail_returns_lightweight_detail_contract(client, tmp_path, monkeypatch):
    review_root = tmp_path / "manual_review"
    relative_path = "unparsed/My Series/Season 1/My Series S01E02.mkv"
    _create_review_file(review_root, relative_path, mtime=1_713_398_400)
    monkeypatch.setattr(main_module, "_manual_review_root", lambda: review_root)
    monkeypatch.setattr(
        main_module,
        "_build_auto_parse_payload",
        lambda item_path, review_root: {
            "status": "parsed",
            "reason": None,
            "target_path": "/library/My Series/Season 1/My Series S01E02.mkv",
            "target_exists": False,
            "score_summary": "score",
            "parsed": {
                "title": "My Series",
                "season": 1,
                "episode": 2,
                "extension": ".mkv",
            },
        },
    )

    response = client.get(
        f"/api/mobile/review/{_review_item_id(relative_path)}",
        headers={"Accept-Language": "en"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["reviewItemId"] == _review_item_id(relative_path)
    assert payload["title"] == "My Series"
    assert payload["state"] == "pending"
    assert payload["failureReason"] == "Could not reliably parse title or season/episode"
    assert payload["source"] == {
        "fileName": "My Series S01E02.mkv",
        "episodeHint": "Episode 2",
    }
    assert payload["suggestedTarget"] == {
        "seriesTitle": "My Series",
        "episodeLabel": "Episode 2",
    }
    assert payload["actions"] == {
        "canRetryParse": True,
        "canManualPublish": True,
        "canDelete": True,
    }
    assert "item" not in payload
    assert "auto_parse" not in payload


def test_mobile_review_retry_parse_uses_existing_review_helpers(client, tmp_path, monkeypatch):
    review_root = tmp_path / "manual_review"
    relative_path = "unparsed/My Series/Season 1/My Series S01E02.mkv"
    _create_review_file(review_root, relative_path, mtime=1_713_398_400)
    monkeypatch.setattr(main_module, "_manual_review_root", lambda: review_root)
    monkeypatch.setattr(
        main_module,
        "_build_auto_parse_payload",
        lambda item_path, review_root: {
            "status": "parsed",
            "reason": None,
            "target_path": "/library/My Series/Season 1/My Series S01E02.mkv",
            "target_exists": False,
            "score_summary": "score",
            "parsed": {
                "title": "My Series",
                "season": 1,
                "episode": 2,
                "extension": ".mkv",
            },
        },
    )
    captured: dict[str, object] = {}

    def fake_publish(media, *, review_root):
        captured["media"] = media
        return {"target": "/library/My Series/Season 1/My Series S01E02.mkv"}

    monkeypatch.setattr(
        main_module,
        "_publish_review_media",
        fake_publish,
    )
    monkeypatch.setattr(main_module, "append_event", lambda **kwargs: captured.setdefault("event", kwargs))

    response = client.post(f"/api/mobile/review/{_review_item_id(relative_path)}/retry-parse")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["action"] == "retry-parse"
    assert payload["reviewItemId"] == _review_item_id(relative_path)
    media = captured["media"]
    assert media.title == "My Series"
    assert media.season == 1
    assert media.episode == 2


def test_mobile_review_manual_publish_uses_defaults_when_body_is_omitted(client, tmp_path, monkeypatch):
    review_root = tmp_path / "manual_review"
    relative_path = "unparsed/My Series/Season 1/My Series S01E02.mkv"
    _create_review_file(review_root, relative_path, mtime=1_713_398_400)
    monkeypatch.setattr(main_module, "_manual_review_root", lambda: review_root)
    monkeypatch.setattr(
        main_module,
        "_build_auto_parse_payload",
        lambda item_path, review_root: {
            "status": "parsed",
            "reason": None,
            "target_path": "/library/My Series/Season 1/My Series S01E02.mkv",
            "target_exists": False,
            "score_summary": "score",
            "parsed": {
                "title": "My Series",
                "season": 1,
                "episode": 2,
                "extension": ".mkv",
            },
        },
    )
    captured: dict[str, object] = {}

    def fake_publish(media, *, review_root):
        captured["media"] = media
        return {"target": "/library/My Series/Season 1/My Series S01E02.mkv"}

    monkeypatch.setattr(
        main_module,
        "_publish_review_media",
        fake_publish,
    )
    monkeypatch.setattr(main_module, "append_event", lambda **kwargs: captured.setdefault("event", kwargs))

    response = client.post(f"/api/mobile/review/{_review_item_id(relative_path)}/manual-publish")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["action"] == "manual-publish"
    assert payload["reviewItemId"] == _review_item_id(relative_path)
    media = captured["media"]
    assert media.title == "My Series"
    assert media.season == 1
    assert media.episode == 2


def test_mobile_review_delete_returns_action_payload(client, tmp_path, monkeypatch):
    review_root = tmp_path / "manual_review"
    relative_path = "failed/My Series/Season 1/My Series S01E02.mkv"
    item_path = _create_review_file(review_root, relative_path, mtime=1_713_398_400)
    monkeypatch.setattr(main_module, "_manual_review_root", lambda: review_root)
    monkeypatch.setattr(main_module, "append_event", lambda **kwargs: None)

    response = client.delete(f"/api/mobile/review/{_review_item_id(relative_path)}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["action"] == "delete"
    assert payload["reviewItemId"] == _review_item_id(relative_path)
    assert not item_path.exists()
