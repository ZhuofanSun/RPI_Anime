from __future__ import annotations

from pathlib import Path
import re

from anime_ops_ui import main as main_module
from anime_ops_ui.navigation import EXTERNAL_SERVICES, INTERNAL_PAGES
from anime_ops_ui.services.log_service import build_logs_payload
from anime_ops_ui.services.navigation_state_service import build_navigation_state
from anime_ops_ui.services.overview_service import build_overview_payload
from anime_ops_ui.services.postprocessor_service import build_postprocessor_payload
from anime_ops_ui.services.review_service import build_manual_review_payload
from anime_ops_ui.services.review_service import build_manual_review_item_payload
from anime_ops_ui.services.tailscale_service import build_tailscale_payload


def _script_text(name: str) -> str:
    return (main_module.APP_DIR / "static" / name).read_text(encoding="utf-8")


def _payload_paths(name: str) -> set[str]:
    normalized_paths = set()
    ignored_suffixes = {"length", "map"}
    for match in re.findall(r"payload(?:\.[A-Za-z_][A-Za-z0-9_]*)+", _script_text(name)):
        path = match.removeprefix("payload.")
        segments = path.split(".")
        if segments[-1] in ignored_suffixes:
            segments = segments[:-1]
        normalized_paths.add(".".join(segments))
    return {path for path in normalized_paths if path}


def _payload_has_path(payload: dict, path: str) -> bool:
    current: object = payload
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return False
        current = current[segment]
    return True


def _assert_payload_matches_page_contract(
    *,
    payload: dict,
    script_name: str,
    ignored_paths: set[str] | None = None,
) -> None:
    ignored = ignored_paths or set()
    missing = sorted(
        path
        for path in _payload_paths(script_name)
        if path not in ignored and not _payload_has_path(payload, path)
    )
    assert missing == []


def test_tailscale_payload_matches_page_contract(monkeypatch):
    tailscale_state = {
        "BackendState": "Running",
        "Health": [],
        "Self": {
            "HostName": "sunzhuofan",
            "DNSName": "rpi.tail9ac25e.ts.net.",
            "Online": True,
            "TailscaleIPs": ["100.123.232.73", "fd7a:115c:a1e0::1"],
            "CurAddr": "100.64.0.5:41641",
            "Relay": "yyz",
            "RxBytes": 128,
            "TxBytes": 256,
        },
        "Peer": {
            "mac": {
                "HostName": "mbp",
                "DNSName": "mbp.tail9ac25e.ts.net.",
                "Online": True,
                "OS": "macOS",
                "TailscaleIPs": ["100.70.0.2", "fd7a:115c:a1e0::2"],
                "CurAddr": "100.70.0.2:41641",
                "Relay": "yyz",
                "RxBytes": 512,
                "TxBytes": 1024,
                "LastSeen": "2026-04-08T12:00:00+00:00",
                "LastHandshake": "2026-04-08T12:00:00+00:00",
                "KeyExpiry": "2026-05-08T12:00:00+00:00",
                "ExitNode": False,
                "ExitNodeOption": True,
                "Active": True,
            }
        },
    }
    prefs = {"WantRunning": True, "LoggedOut": False}

    monkeypatch.setattr(main_module, "_tailscale_status", lambda socket_path: (tailscale_state, None))
    monkeypatch.setattr(main_module, "_tailscale_prefs", lambda socket_path: (prefs, None))

    payload = build_tailscale_payload()
    _assert_payload_matches_page_contract(
        payload=payload,
        script_name="tailscale.js",
        ignored_paths={"auth_url", "detail", "message"},
    )


def test_manual_review_item_payload_matches_page_contract(monkeypatch, tmp_path):
    review_root = tmp_path / "manual_review"
    item_root = review_root / "unparsed" / "My Series" / "Season 1"
    item_root.mkdir(parents=True)
    current_path = item_root / "My Series S01E01.mkv"
    sibling_path = item_root / "My Series S01E01 v2.mkv"
    current_path.write_bytes(b"episode")
    sibling_path.write_bytes(b"episode-v2")

    monkeypatch.setattr(main_module, "_manual_review_root", lambda: review_root)
    monkeypatch.setattr(
        main_module,
        "_build_auto_parse_payload",
        lambda item_path, review_root: {
            "status": "parsed",
            "reason": None,
            "target_path": "/srv/anime-data/library/seasonal/My Series/Season 1/My Series S01E01.mkv",
            "target_exists": False,
            "score_summary": "subtitle +1080p",
            "parsed": {"title": "My Series", "season": 1, "episode": 1, "extension": ".mkv"},
        },
    )
    monkeypatch.setattr(
        main_module,
        "_manual_publish_defaults",
        lambda item, auto_parse: {"title": "My Series", "season": 1, "episode": 1},
    )

    payload = build_manual_review_item_payload("unparsed__My Series__Season 1__My Series S01E01.mkv")
    _assert_payload_matches_page_contract(
        payload=payload,
        script_name="ops-review-item.js",
        ignored_paths={"detail", "message"},
    )


def test_manual_review_payload_matches_page_contract(monkeypatch, tmp_path):
    review_root = tmp_path / "manual_review"
    episode_root = review_root / "bucket_a" / "My Series" / "Season 1"
    episode_root.mkdir(parents=True)
    (episode_root / "My Series S01E01.mkv").write_bytes(b"episode")

    monkeypatch.setattr(main_module, "_manual_review_root", lambda: review_root)

    payload = build_manual_review_payload()
    _assert_payload_matches_page_contract(payload=payload, script_name="ops-review.js")


def test_logs_payload_matches_page_contract(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "read_events",
        lambda: [{"source": "ops-ui", "level": "info", "action": "startup", "message": "started", "details": {}}],
    )
    monkeypatch.setattr(main_module, "event_log_cap", lambda: 100)
    monkeypatch.setattr(main_module, "event_log_path", lambda: Path("/tmp/events.json"))

    payload = build_logs_payload()
    _assert_payload_matches_page_contract(
        payload=payload,
        script_name="logs.js",
        ignored_paths={"message"},
    )


def test_postprocessor_payload_matches_page_contract(monkeypatch, tmp_path):
    source_root = tmp_path / "downloads" / "Bangumi"
    target_root = tmp_path / "library" / "seasonal"
    review_root = tmp_path / "processing" / "manual_review"
    source_root.mkdir(parents=True)
    target_root.mkdir(parents=True)
    review_root.mkdir(parents=True)

    monkeypatch.setattr(
        main_module,
        "_postprocessor_paths",
        lambda: {
            "anime_data_root": tmp_path,
            "source_root": source_root,
            "target_root": target_root,
            "review_root": review_root,
            "title_map": tmp_path / "title_mappings.toml",
        },
    )
    monkeypatch.setattr(main_module, "_glances_containers_snapshot", lambda: ({}, None))
    monkeypatch.setattr(main_module, "_qb_snapshot", lambda: (None, "qB unavailable"))
    monkeypatch.setattr(main_module, "read_events", lambda limit=200: [])
    monkeypatch.setattr(main_module, "_count_media_files", lambda root: 0)

    payload = build_postprocessor_payload()
    _assert_payload_matches_page_contract(payload=payload, script_name="postprocessor.js")


def test_overview_payload_matches_phase2_dashboard_app_contract(monkeypatch, tmp_path):
    data_root = tmp_path / "anime-data"
    collection_root = tmp_path / "anime-collection"
    data_root.mkdir()
    collection_root.mkdir()
    (data_root / "library" / "seasonal").mkdir(parents=True)
    (data_root / "downloads" / "Bangumi").mkdir(parents=True)
    (data_root / "processing" / "manual_review").mkdir(parents=True)

    containers = [
        {"name": "jellyfin", "status": "running", "uptime": "1h"},
        {"name": "qbittorrent", "status": "running", "uptime": "1h"},
        {"name": "autobangumi", "status": "exited", "uptime": "1h"},
        {"name": "glances", "status": "running", "uptime": "1h"},
        {"name": "anime-postprocessor", "status": "running", "uptime": "1h"},
        {"name": "homepage", "status": "running", "uptime": "1h"},
    ]

    def fake_get_json(url: str, *, timeout: int = 5):
        if url.endswith("/quicklook"):
            return {"cpu": 12, "cpu_name": "Raspberry Pi 4"}, None
        if url.endswith("/containers"):
            return containers, None
        if url.endswith("/mem"):
            return {"percent": 45, "available": 1024}, None
        if url.endswith("/uptime"):
            return "25:10:00", None
        if url.endswith("/load"):
            return {"min1": 0.4, "min5": 0.5, "min15": 0.6}, None
        if url.endswith("/sensors"):
            return [{"value": 50.0}], None
        return None, "unexpected"

    monkeypatch.setattr(
        main_module,
        "_env",
        lambda name, default: {
            "ANIME_DATA_ROOT": str(data_root),
            "ANIME_COLLECTION_ROOT": str(collection_root),
            "HOMEPAGE_BASE_HOST": "ops.local",
            "TAILSCALE_SOCKET": "/var/run/tailscale/tailscaled.sock",
        }.get(name, default),
    )
    monkeypatch.setattr(main_module, "_sample_history_once", lambda: None)
    monkeypatch.setattr(main_module, "_safe_get_json", fake_get_json)
    monkeypatch.setattr(
        main_module,
        "_tailscale_status",
        lambda socket_path: (
            {
                "BackendState": "Running",
                "Self": {
                    "HostName": "sunzhuofan",
                    "DNSName": "rpi.tail9ac25e.ts.net.",
                    "Online": True,
                    "TailscaleIPs": ["100.123.232.73", "fd7a:115c:a1e0::1"],
                },
                "Peer": {},
            },
            None,
        ),
    )
    monkeypatch.setattr(
        main_module,
        "_qb_snapshot",
        lambda: (
            {
                "category": "Bangumi",
                "task_count": 3,
                "active_downloads": 1,
                "active_seeds": 2,
                "download_speed": 2048,
                "upload_speed": 1024,
            },
            None,
        ),
    )
    monkeypatch.setattr(main_module, "_fan_state_snapshot", lambda: ({"updated_ts": 0.0}, None))
    monkeypatch.setattr(main_module, "_series_window_hours", lambda: 24)
    monkeypatch.setattr(main_module, "_upload_window_days", lambda: 7)
    monkeypatch.setattr(main_module, "_series_values", lambda name, window_hours: ([10.0, 20.0], [10.0, 20.0]))
    monkeypatch.setattr(
        main_module,
        "_daily_volume_bars",
        lambda *, days, daily_key: ([{"label": "04-07", "value": 1024, "value_label": "1.0 KB"}], [1024.0]),
    )
    monkeypatch.setattr(main_module, "_count_media_files", lambda root: 0)
    monkeypatch.setattr(main_module, "_count_series_dirs", lambda root: 0)
    monkeypatch.setattr(main_module, "_history_file", lambda: tmp_path / "history.json")
    monkeypatch.setattr(main_module, "read_events", lambda limit=300: [])

    payload = build_overview_payload()

    _assert_payload_matches_page_contract(
        payload=payload,
        script_name="app.js",
        ignored_paths={"message", "reload_after_seconds"},
    )
    assert isinstance(payload["services"], list) and payload["services"]
    assert isinstance(payload["queue_cards"], list) and payload["queue_cards"]
    assert {"label", "value", "detail"}.issubset(payload["queue_cards"][0].keys())
    service = payload["services"][0]
    assert {
        "name",
        "href",
        "description",
        "status",
        "meta",
        "uptime",
        "restart_target",
        "restart_label",
    }.issubset(service.keys())
    internal_service = next(item for item in payload["services"] if item["id"] == "ops-review")
    assert {
        "internal",
        "restart_target",
        "restart_label",
        "restart_requires_reload",
        "restart_name",
    }.issubset(internal_service.keys())


def test_logs_page_uses_flash_helpers_with_logs_container():
    script = _script_text("logs.js")

    assert re.search(r"setFlash\(\s*logsFlash\s*,", script)
    assert re.search(r"clearFlash\(\s*logsFlash\s*\)", script)


def test_shell_script_preserves_active_state_by_page_key():
    script = _script_text("shell.js")

    assert "body.dataset.page" in script
    assert 'item.id === pageKey' in script


def test_shell_script_nav_toggle_controls_real_region_visibility():
    script = _script_text("shell.js")

    assert "aria-controls" in script
    assert ".hidden =" in script


def test_navigation_state_payload_matches_shell_contract(monkeypatch, tmp_path):
    review_root = tmp_path / "manual_review"
    review_root.mkdir(parents=True)

    monkeypatch.setattr(main_module, "_manual_review_root", lambda: review_root)
    monkeypatch.setattr(main_module, "_count_media_files", lambda root: 3 if root == review_root else 0)
    monkeypatch.setattr(main_module, "read_events", lambda limit=300: [{"level": "error"}])
    monkeypatch.setattr(
        main_module,
        "_latest_sampled_metric",
        lambda name: {
            "qb_active_downloads": 2.0,
            "tailscale_online": 1.0,
        }.get(name),
    )
    monkeypatch.setattr(
        main_module,
        "_env",
        lambda name, default: {
            "HOMEPAGE_BASE_HOST": "ops.local",
            "JELLYFIN_PORT": "8096",
            "QBITTORRENT_WEBUI_PORT": "8080",
            "AUTOBANGUMI_PORT": "7892",
            "GLANCES_PORT": "61208",
        }.get(name, default),
    )

    payload = build_navigation_state()
    _assert_payload_matches_page_contract(payload=payload, script_name="shell.js")

    assert payload["internal"]
    assert payload["external"]
    assert {item["id"] for item in payload["internal"]} == set(INTERNAL_PAGES.keys())
    assert {item["id"] for item in payload["external"]} == set(EXTERNAL_SERVICES.keys())

    required_internal_keys = {"id", "label", "icon", "target", "path", "href", "badge", "tone"}
    required_external_keys = {"id", "label", "icon", "target", "href", "badge", "tone"}
    assert all(required_internal_keys.issubset(item.keys()) for item in payload["internal"])
    assert all(required_external_keys.issubset(item.keys()) for item in payload["external"])
