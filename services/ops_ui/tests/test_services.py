from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import types

import pytest

import anime_ops_ui as package_module
from anime_ops_ui import main as main_module
from anime_ops_ui.services import postprocessor_service as postprocessor_service_module
from anime_ops_ui.services import overview_service as overview_service_module
from anime_ops_ui.services.dashboard_sections import build_summary_strip
from anime_ops_ui.services.log_service import build_logs_payload
from anime_ops_ui.services.overview_service import build_overview_payload, build_service_summary
from anime_ops_ui.services.postprocessor_service import build_postprocessor_payload
from anime_ops_ui.services.review_service import build_manual_review_item_payload, build_manual_review_payload
from anime_ops_ui.services.tailscale_service import build_tailscale_payload
from anime_postprocessor import eventlog as eventlog_module


def test_ensure_canonical_main_module_alias_maps_dunder_main_to_package_module():
    module_map = {"__main__": types.ModuleType("__main__")}

    main_module._ensure_canonical_main_module_alias(
        current_name="__main__",
        sys_modules=module_map,
    )

    assert module_map["anime_ops_ui.main"] is module_map["__main__"]


def test_runtime_main_module_prefers_matching_dunder_main_module():
    dunder_main = types.ModuleType("__main__")
    dunder_main.__file__ = str(Path(main_module.__file__).resolve())
    imported_main = types.ModuleType("anime_ops_ui.main")

    resolved = package_module.runtime_main_module(
        sys_modules={
            "__main__": dunder_main,
            "anime_ops_ui.main": imported_main,
        },
        package_main_path=Path(main_module.__file__).resolve(),
    )

    assert resolved is dunder_main


def test_build_service_summary_counts_tailscaled():
    summary = build_service_summary(
        containers={
            "jellyfin": {"status": "running"},
            "qbittorrent": {"status": "exited"},
        },
        tailscale_running=True,
        locale="en",
    )

    assert summary["value"] == "2 online"
    assert summary["detail"] == "3 total · Docker + tailscaled"


def test_build_summary_strip_counts_library_ready_schedule_items_across_visible_hidden_and_unknown():
    summary_strip = build_summary_strip(
        active_downloads=7,
        review_count=2,
        diagnostics=[],
        weekly_schedule={
            "days": [
                {
                    "items": [{"is_library_ready": True}, {"is_library_ready": False}],
                    "hidden_items": [{"is_library_ready": True}],
                },
                {
                    "items": [],
                    "hidden_items": [{"is_library_ready": True}, {"is_library_ready": True}],
                },
                {
                    "items": [{"is_library_ready": False}],
                    "hidden_items": [],
                },
                {
                    "items": [],
                    "hidden_items": [],
                },
                {
                    "items": [{"is_library_ready": True}],
                    "hidden_items": [{"is_library_ready": False}],
                },
                {
                    "items": [],
                    "hidden_items": [],
                },
                {
                    "items": [{"is_library_ready": True}],
                    "hidden_items": [{"is_library_ready": True}],
                },
            ],
            "unknown": {
                "items": [{"is_library_ready": True}, {"is_library_ready": False}],
                "hidden_items": [{"is_library_ready": True}],
            },
        },
        locale="en",
    )

    assert summary_strip[0]["answer"] == "9 ready in library"


def test_build_overview_payload_uses_public_host_for_schedule_and_service_links(monkeypatch, tmp_path):
    data_root = tmp_path / "anime-data"
    collection_root = tmp_path / "anime-collection"
    data_root.mkdir()
    collection_root.mkdir()
    (data_root / "library" / "seasonal").mkdir(parents=True)
    (data_root / "downloads" / "Bangumi").mkdir(parents=True)
    (data_root / "processing" / "manual_review").mkdir(parents=True)

    monkeypatch.setattr(
        main_module,
        "_env",
        lambda name, default: {
            "ANIME_DATA_ROOT": str(data_root),
            "ANIME_COLLECTION_ROOT": str(collection_root),
            "HOMEPAGE_BASE_HOST": "sunzhuofan.local",
            "TAILSCALE_SOCKET": "/var/run/tailscale/tailscaled.sock",
            "AUTOBANGUMI_API_URL": "",
        }.get(name, default),
    )
    monkeypatch.setattr(main_module, "_sample_history_once", lambda: None)
    monkeypatch.setattr(main_module, "_safe_get_json", lambda *args, **kwargs: ({}, None))
    monkeypatch.setattr(main_module, "_tailscale_status", lambda *args, **kwargs: ({}, None))
    monkeypatch.setattr(main_module, "_qb_snapshot", lambda: (None, None))
    monkeypatch.setattr(main_module, "_fan_state_snapshot", lambda: (None, None))
    monkeypatch.setattr(main_module, "read_events", lambda limit=300: [])

    captured: dict[str, str] = {}

    def fake_phase4_snapshot(**kwargs):
        captured["base_host"] = kwargs["base_host"]
        return {
            "weekly_schedule": {
                "week_key": "2026-W15",
                "today_weekday": 2,
                "days": [
                    {
                        "weekday": index,
                        "label": label,
                        "is_today": index == 2,
                        "items": [],
                        "hidden_items": [],
                        "has_hidden_items": False,
                    }
                    for index, label in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
                ],
                "unknown": {
                    "label": "Unknown",
                    "hint": "Drag to assign a broadcast day",
                    "items": [],
                    "hidden_items": [],
                    "has_hidden_items": False,
                },
            }
        }

    monkeypatch.setattr(overview_service_module, "build_phase4_schedule_snapshot", fake_phase4_snapshot)

    payload = build_overview_payload(locale="en", public_host="100.88.77.66")

    jellyfin_row = next(item for item in payload["service_rows"] if item["id"] == "jellyfin")

    assert captured["base_host"] == "100.88.77.66"
    assert payload["hero"]["host"] == "100.88.77.66"
    assert jellyfin_row["href"] == "http://100.88.77.66:8096"


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

    payload = build_logs_payload(source="ops-ui", level="error", search="boom", limit=100, locale="en")

    assert payload["matched_count"] == 1
    assert payload["items"][0]["action"] == "save"
    assert payload["summary_cards"][0]["value"] == "1"
    assert payload["storage_path"] == "/tmp/events.json"
    assert payload["title"] == "Logs"
    assert payload["summary_cards"][0]["label"] == "Visible"
    assert payload["copy"]["filters"]["all_sources"] == "All Sources"
    assert payload["copy"]["clear"]["success_message"] == "Cleared {count} structured log entries."


def test_read_events_returns_empty_when_event_log_parent_cannot_be_created(monkeypatch):
    monkeypatch.setattr(
        eventlog_module,
        "event_log_path",
        lambda: Path("/srv/anime-data/appdata/ops-ui/events.json"),
    )

    def raising_mkdir(self, parents=False, exist_ok=False):
        raise OSError(30, "Read-only file system")

    monkeypatch.setattr(Path, "mkdir", raising_mkdir)

    assert eventlog_module.read_events(limit=10) == []


def test_build_manual_review_payload_reads_temp_tree(monkeypatch, tmp_path):
    review_root = tmp_path / "manual_review"
    episode_root = review_root / "unparsed" / "My Series" / "Season 1"
    episode_root.mkdir(parents=True)
    media_path = episode_root / "My Series S01E01.mkv"
    media_path.write_bytes(b"media")

    monkeypatch.setattr(main_module, "_manual_review_root", lambda: review_root)

    payload = build_manual_review_payload(locale="en")

    assert payload["total_files"] == 1
    assert payload["summary_cards"][0]["value"] == "1"
    assert payload["buckets"][0]["bucket"] == "unparsed"
    assert payload["buckets"][0]["label"] == "Unparsed"
    assert payload["items"][0]["series_name"] == "My Series"
    assert payload["items"][0]["bucket_label"] == "Unparsed"
    assert payload["items"][0]["reason"] == "Could not reliably parse title or season/episode"
    assert payload["summary_cards"][0]["label"] == "Review Files"
    assert payload["copy"]["filter_all"] == "All Buckets"

    item_payload = build_manual_review_item_payload(payload["items"][0]["id"], locale="en")
    assert item_payload["item"]["filename"] == "My Series S01E01.mkv"
    assert item_payload["item"]["bucket_label"] == "Unparsed"
    assert item_payload["item"]["reason"] == "Could not reliably parse title or season/episode"
    assert item_payload["path"].endswith("My Series S01E01.mkv")
    assert item_payload["breadcrumbs"][0]["label"] == "Dashboard"
    assert item_payload["copy"]["actions"]["delete"]["confirm_title"] == "Delete File"

    zh_payload = build_manual_review_payload(locale="zh-Hans")
    assert zh_payload["title"] == "人工审核"
    assert zh_payload["summary_cards"][0]["label"] == "待审文件"
    assert zh_payload["buckets"][0]["bucket"] == "unparsed"
    assert zh_payload["buckets"][0]["label"] == "无法解析"
    assert zh_payload["items"][0]["bucket_label"] == "无法解析"
    assert zh_payload["copy"]["filter_all"] == "全部分组"


def test_build_manual_review_item_payload_localizes_unparseable_reason(monkeypatch, tmp_path):
    review_root = tmp_path / "manual_review"
    item_root = review_root / "unparsed" / "My Series" / "Season 1"
    item_root.mkdir(parents=True)
    media_path = item_root / "My Series S01E01.mkv"
    media_path.write_bytes(b"episode")

    monkeypatch.setattr(main_module, "_manual_review_root", lambda: review_root)
    monkeypatch.setattr(
        main_module,
        "_build_auto_parse_payload",
        lambda item_path, review_root: {
            "status": "unparsed",
            "reason": "cannot parse season/episode",
            "target_path": None,
            "target_exists": False,
            "score_summary": None,
            "parsed": None,
        },
    )
    monkeypatch.setattr(
        main_module,
        "_manual_publish_defaults",
        lambda item, auto_parse: {"title": "My Series", "season": 1, "episode": 1},
    )

    payload = build_manual_review_item_payload(
        "unparsed__My Series__Season 1__My Series S01E01.mkv",
        locale="en",
    )

    assert payload["auto_parse"]["status"] == "unparsed"
    assert payload["auto_parse"]["reason"] == "Could not parse season or episode"


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
        lambda *, state, completed_entries, now_ts, wait_timeout: (True, "best candidate already completed"),
    )
    monkeypatch.setattr(main_module, "read_events", lambda limit=200: [{"source": "postprocessor", "message": "started"}])
    monkeypatch.setattr(main_module, "_count_media_files", lambda root: 0)

    payload = build_postprocessor_payload(locale="en")

    assert payload["summary_cards"][0]["value"] == "Running"
    assert payload["summary_cards"][1]["value"] == "1"
    assert payload["worker_badge"] == "Running"
    assert payload["sections"][0]["title"] == "Ready On Next Tick"
    assert payload["sections"][0]["items"][0]["title"] == "dr-stone"
    assert payload["sections"][0]["items"][0]["reason"] == "Ready because the top-scoring completed candidate is available"
    assert payload["config_cards"][0]["label"] == "Source Root"
    assert payload["copy"]["field_labels"]["best_overall"] == "Best Overall"

    payload_zh = build_postprocessor_payload(locale="zh-Hans")
    assert payload_zh["summary_cards"][0]["value"] == "运行中"
    assert payload_zh["worker_badge"] == "运行中"


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

    payload = build_tailscale_payload(locale="en")

    assert payload["status"]["backend_state"] == "Running"
    assert payload["status"]["reachable"] is True
    assert payload["summary_cards"][2]["value"] == "0"
    assert payload["current_node"]["control_action"] == "stop"
    assert payload["control"]["label"] == "Stop Tailscale"
    assert payload["copy"]["peer_fields"]["ipv6"] == "IPv6"
    assert payload["copy"]["action"]["in_progress"] == "Running the Tailscale control action."


def test_restart_service_now_returns_structured_manual_auth_signal_for_tailscale(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "_tailscale_restart_action",
        lambda socket_path: {
            "ok": True,
            "action": "start",
            "message": "Tailscale backend 已开启，但当前版本没有回传登录链接。请在树莓派终端执行 sudo tailscale login 或 sudo tailscale up 完成授权。",
            "auth_required": True,
            "auth_mode": "manual",
        },
    )
    monkeypatch.setattr(main_module, "_env", lambda name, default: "/var/run/tailscale/tailscaled.sock" if name == "TAILSCALE_SOCKET" else default)

    payload = main_module._restart_service_now("tailscale")

    assert payload["target"] == "tailscale"
    assert payload["label"] == "Tailscale"
    assert payload["auth_required"] is True
    assert payload["auth_mode"] == "manual"
    assert payload.get("auth_url") is None


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
    monkeypatch.setattr(
        overview_service_module,
        "build_phase4_schedule_snapshot",
        lambda **kwargs: {
            "weekly_schedule": {
                "week_key": "2026-W15",
                "today_weekday": 2,
                "days": [
                    {
                        "weekday": 0,
                        "label": "Mon",
                        "is_today": False,
                        "items": [{"is_library_ready": True}],
                        "hidden_items": [],
                        "has_hidden_items": False,
                    },
                    {
                        "weekday": 1,
                        "label": "Tue",
                        "is_today": False,
                        "items": [],
                        "hidden_items": [{"is_library_ready": True}],
                        "has_hidden_items": True,
                    },
                    {
                        "weekday": 2,
                        "label": "Wed",
                        "is_today": True,
                        "items": [],
                        "hidden_items": [],
                        "has_hidden_items": False,
                    },
                    {
                        "weekday": 3,
                        "label": "Thu",
                        "is_today": False,
                        "items": [],
                        "hidden_items": [],
                        "has_hidden_items": False,
                    },
                    {
                        "weekday": 4,
                        "label": "Fri",
                        "is_today": False,
                        "items": [],
                        "hidden_items": [],
                        "has_hidden_items": False,
                    },
                    {
                        "weekday": 5,
                        "label": "Sat",
                        "is_today": False,
                        "items": [],
                        "hidden_items": [],
                        "has_hidden_items": False,
                    },
                    {
                        "weekday": 6,
                        "label": "Sun",
                        "is_today": False,
                        "items": [],
                        "hidden_items": [],
                        "has_hidden_items": False,
                    },
                ],
                "unknown": {
                    "label": "Unknown",
                    "hint": "Drag to assign a broadcast day",
                    "items": [{"is_library_ready": True}],
                    "hidden_items": [],
                    "has_hidden_items": False,
                },
            },
        },
    )

    payload = build_overview_payload(locale="en")

    assert payload["page_key"] == "dashboard"
    assert payload["title"] == "RPI Anime Ops"
    assert payload["services"][0]["name"] == "Jellyfin"
    assert payload["system_cards"][4]["label"] == "Services"
    assert payload["system_cards"][5]["detail"] == "Data disk is not mounted or readable"
    assert payload["queue_cards"][0]["value"] == "3"
    jellyfin = payload["services"][0]
    assert jellyfin["description"] == "Private library and playback entrypoint"
    assert jellyfin["meta"] == "Media server"
    assert jellyfin["uptime"] == "1h"
    assert jellyfin["restart_target"] == "jellyfin"
    assert jellyfin["restart_label"] == "Restart"
    assert payload["queue_cards"][3]["detail"] == "Data disk unavailable"
    assert payload["queue_cards"][4]["detail"] == "Data disk unavailable"
    assert payload["network_cards"][2]["detail"] == "0 online"
    assert payload["trend_cards"][2]["detail"] == "24h avg 15 B/s · all clients"
    assert payload["trend_cards"][3]["detail"] == "7 day total · qBittorrent"
    assert {"label", "value", "detail"}.issubset(payload["queue_cards"][0].keys())
    ops_review_legacy = next(item for item in payload["services"] if item["id"] == "ops-review")
    assert ops_review_legacy["internal"] is True
    assert ops_review_legacy["restart_target"] == "homepage"
    assert ops_review_legacy["restart_requires_reload"] is True
    assert ops_review_legacy["restart_name"] == "Ops UI"
    assert {
        "hero",
        "summary_strip",
        "pipeline_cards",
        "system_cards",
        "network_cards",
        "trend_cards",
        "service_rows",
        "stack_control",
        "diagnostics",
        "last_updated",
    }.issubset(payload.keys())
    assert payload["hero"]["title"] == "RPI Anime Ops"
    assert payload["hero"]["eyebrow"] == "Control surface"
    assert payload["hero"]["host"] == "sunzhuofan.local"
    assert payload["summary_strip"][0] == {
        "question": "What is worth watching today?",
        "answer": "3 ready in library",
        "tone": "teal",
    }
    assert payload["summary_strip"][1]["question"] == "Is download and library ingest healthy?"
    assert payload["summary_strip"][2]["question"] == "Are device health and remote access stable?"
    assert set(payload["summary_strip"][1].keys()) == {"question", "answer", "tone"}
    assert set(payload["summary_strip"][2].keys()) == {"question", "answer", "tone"}
    assert payload["pipeline_cards"] == payload["queue_cards"]
    assert payload["service_rows"][0]["id"] == "jellyfin"
    assert payload["service_rows"][0]["status"] == "running"
    ops_review_row = next(item for item in payload["service_rows"] if item["id"] == "ops-review")
    assert ops_review_row["internal"] is True
    assert ops_review_row["href"].endswith("/ops-review")
    assert ops_review_row["meta"] == "Data disk unavailable"
    assert ops_review_row["uptime"] == "Review workspace"
    assert ops_review_row["restart_target"] == "homepage"
    assert ops_review_row["restart_label"] == "Restart UI"
    assert ops_review_row["restart_requires_reload"] is True
    assert ops_review_row["restart_name"] == "Ops UI"
    logs_service = next(item for item in payload["services"] if item["id"] == "logs")
    assert logs_service["description"] == "Structured logs, source filtering, and cleanup"
    logs_row = next(item for item in payload["service_rows"] if item["id"] == "logs")
    assert logs_row["meta"] == "0 events"
    assert logs_row["uptime"] == "cap 1500 events"
    assert "today_focus" not in payload
