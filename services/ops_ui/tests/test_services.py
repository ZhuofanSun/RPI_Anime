from __future__ import annotations

from types import SimpleNamespace

from anime_ops_ui import main as main_module
from anime_ops_ui.services import postprocessor_service as postprocessor_service_module
from anime_ops_ui.services.log_service import build_logs_payload
from anime_ops_ui.services.overview_service import build_overview_payload, build_service_summary
from anime_ops_ui.services.postprocessor_service import build_postprocessor_payload
from anime_ops_ui.services.review_service import build_manual_review_item_payload, build_manual_review_payload
from anime_ops_ui.services.tailscale_service import build_tailscale_payload


def test_build_service_summary_counts_tailscaled():
    summary = build_service_summary(
        containers={
            "jellyfin": {"status": "running"},
            "qbittorrent": {"status": "exited"},
        },
        tailscale_running=True,
    )

    assert summary["value"] == "2 online"
    assert summary["detail"] == "3 total · Docker + tailscaled"


def test_build_logs_payload_filters_by_source_level_and_search(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "read_events",
        lambda: [
            {"source": "ops-ui", "level": "info", "action": "restart", "message": "stack restarted", "details": {}},
            {"source": "postprocessor", "level": "warning", "action": "publish", "message": "waiting window", "details": {"target": "seasonal"}},
            {"source": "ops-ui", "level": "error", "action": "save", "message": "failed to save", "details": {"error": "boom"}},
        ],
    )
    monkeypatch.setattr(main_module, "event_log_cap", lambda: 1500)
    monkeypatch.setattr(main_module, "event_log_path", lambda: "/tmp/events.json")

    payload = build_logs_payload(source="ops-ui", level="error", search="boom", limit=100)

    assert payload["matched_count"] == 1
    assert payload["items"][0]["action"] == "save"
    assert payload["summary_cards"][0]["value"] == "1"
    assert payload["storage_path"] == "/tmp/events.json"


def test_build_manual_review_payload_reads_temp_tree(monkeypatch, tmp_path):
    review_root = tmp_path / "manual_review"
    episode_root = review_root / "bucket_a" / "My Series" / "Season 1"
    episode_root.mkdir(parents=True)
    media_path = episode_root / "My Series S01E01.mkv"
    media_path.write_bytes(b"media")

    monkeypatch.setattr(main_module, "_manual_review_root", lambda: review_root)

    payload = build_manual_review_payload()

    assert payload["total_files"] == 1
    assert payload["summary_cards"][0]["value"] == "1"
    assert payload["buckets"][0]["bucket"] == "bucket_a"
    assert payload["items"][0]["series_name"] == "My Series"

    item_payload = build_manual_review_item_payload(payload["items"][0]["id"])
    assert item_payload["item"]["filename"] == "My Series S01E01.mkv"
    assert item_payload["path"].endswith("My Series S01E01.mkv")


def test_build_postprocessor_payload_composes_sections(monkeypatch, tmp_path):
    source_root = tmp_path / "downloads" / "Bangumi"
    target_root = tmp_path / "library" / "seasonal"
    review_root = tmp_path / "processing" / "manual_review"
    source_root.mkdir(parents=True)
    target_root.mkdir(parents=True)
    review_root.mkdir(parents=True)

    class FakeKey:
        def __init__(self) -> None:
            self.normalized_title = "dr-stone"
            self.season = 1
            self.episode = 1

    fake_key = FakeKey()
    fake_entry = SimpleNamespace(
        parsed_files=[],
        unparsed_files=[],
        torrent=SimpleNamespace(name="Dr. STONE S01E01", state="uploading", progress=1.0, completed=True),
        content_root=str(source_root),
        media_paths=[],
    )

    monkeypatch.setattr(main_module, "_postprocessor_paths", lambda: {
        "anime_data_root": tmp_path,
        "source_root": source_root,
        "target_root": target_root,
        "review_root": review_root,
        "title_map": tmp_path / "title_mappings.toml",
    })
    monkeypatch.setattr(main_module, "_glances_containers_snapshot", lambda: (
        {"anime-postprocessor": {"status": "running", "uptime": "3m"}},
        None,
    ))
    monkeypatch.setattr(main_module, "_qb_snapshot", lambda: (
        {
            "category": "Bangumi",
            "task_count": 2,
            "active_downloads": 1,
            "active_seeds": 1,
            "download_speed": 1024,
            "upload_speed": 512,
        },
        None,
    ))
    monkeypatch.setattr(
        postprocessor_service_module,
        "QBClient",
        lambda *args, **kwargs: SimpleNamespace(
            auth=lambda: None,
            list_torrents=lambda category=None: [SimpleNamespace()],
        ),
    )
    monkeypatch.setattr(
        main_module,
        "_build_groups",
        lambda torrents, qb, qb_download_root, local_download_root: ({fake_key: [fake_entry]}, []),
    )
    monkeypatch.setattr(
        main_module,
        "_should_process_group",
        lambda *, state, completed_entries, now_ts, wait_timeout: (True, "ready now"),
    )
    monkeypatch.setattr(main_module, "read_events", lambda limit=200: [{"source": "postprocessor", "message": "started"}])
    monkeypatch.setattr(main_module, "_count_media_files", lambda root: 0)

    payload = build_postprocessor_payload()

    assert payload["summary_cards"][0]["value"] == "Running"
    assert payload["summary_cards"][1]["value"] == "1"
    assert payload["sections"][0]["title"] == "Ready On Next Tick"
    assert payload["sections"][0]["items"][0]["title"] == "dr-stone"


def test_build_tailscale_payload_uses_socket_state(monkeypatch):
    tailscale_state = {
        "BackendState": "Running",
        "Health": [],
        "Self": {
            "HostName": "sunzhuofan",
            "DNSName": "rpi.tail9ac25e.ts.net.",
            "Online": True,
            "TailscaleIPs": ["100.123.232.73", "fd7a:115c:a1e0::1"],
        },
        "Peer": {},
    }
    prefs = {"WantRunning": True, "LoggedOut": False}

    monkeypatch.setattr(main_module, "_tailscale_status", lambda socket_path: (tailscale_state, None))
    monkeypatch.setattr(main_module, "_tailscale_prefs", lambda socket_path: (prefs, None))

    payload = build_tailscale_payload()

    assert payload["status"]["backend_state"] == "Running"
    assert payload["status"]["reachable"] is True
    assert payload["summary_cards"][2]["value"] == "0"
    assert payload["current_node"]["control_action"] == "stop"


def test_build_overview_payload_reports_service_summary(monkeypatch, tmp_path):
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

    monkeypatch.setattr(main_module, "_env", lambda name, default: {
        "ANIME_DATA_ROOT": str(data_root),
        "ANIME_COLLECTION_ROOT": str(collection_root),
        "HOMEPAGE_BASE_HOST": "sunzhuofan.local",
        "TAILSCALE_SOCKET": "/var/run/tailscale/tailscaled.sock",
    }.get(name, default))
    monkeypatch.setattr(main_module, "_sample_history_once", lambda: None)
    monkeypatch.setattr(main_module, "_safe_get_json", fake_get_json)
    monkeypatch.setattr(main_module, "_tailscale_status", lambda socket_path: ({
        "BackendState": "Running",
        "Self": {
            "HostName": "sunzhuofan",
            "DNSName": "rpi.tail9ac25e.ts.net.",
            "Online": True,
            "TailscaleIPs": ["100.123.232.73", "fd7a:115c:a1e0::1"],
        },
        "Peer": {},
    }, None))
    monkeypatch.setattr(main_module, "_qb_snapshot", lambda: ({
        "category": "Bangumi",
        "task_count": 3,
        "active_downloads": 1,
        "active_seeds": 2,
        "download_speed": 2048,
        "upload_speed": 1024,
    }, None))
    monkeypatch.setattr(main_module, "_fan_state_snapshot", lambda: ({"updated_ts": 0.0}, None))
    monkeypatch.setattr(main_module, "_series_window_hours", lambda: 24)
    monkeypatch.setattr(main_module, "_upload_window_days", lambda: 7)
    monkeypatch.setattr(main_module, "_series_values", lambda name, window_hours: ([10.0, 20.0], [10.0, 20.0]))
    monkeypatch.setattr(main_module, "_daily_volume_bars", lambda *, days, daily_key: ([{"label": "04-07", "value": 1024, "value_label": "1.0 KB"}], [1024.0]))
    monkeypatch.setattr(main_module, "_count_media_files", lambda root: 0)
    monkeypatch.setattr(main_module, "_count_series_dirs", lambda root: 0)
    monkeypatch.setattr(main_module, "_history_file", lambda: tmp_path / "history.json")
    monkeypatch.setattr(main_module, "read_events", lambda limit=300: [])

    payload = build_overview_payload()

    assert payload["page_key"] == "dashboard"
    assert payload["title"] == "RPI Anime Ops"
    assert payload["services"][0]["name"] == "Jellyfin"
    assert payload["system_cards"][4]["label"] == "Services"
    assert payload["queue_cards"][0]["value"] == "3"
