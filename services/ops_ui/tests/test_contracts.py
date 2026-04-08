from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
import re

import pytest

from anime_ops_ui import main as main_module
from anime_ops_ui.navigation import EXTERNAL_SERVICES, INTERNAL_PAGES, SERVICE_ACTIONS, STACK_ACTION
from anime_ops_ui.services.log_service import build_logs_payload
from anime_ops_ui.services.navigation_state_service import build_navigation_state
from anime_ops_ui.services import overview_service
from anime_ops_ui.services.overview_service import build_overview_payload
from anime_ops_ui.services.postprocessor_service import build_postprocessor_payload
from anime_ops_ui.services.review_service import build_manual_review_payload
from anime_ops_ui.services.review_service import build_manual_review_item_payload
from anime_ops_ui.services.tailscale_service import build_tailscale_payload


def _empty_weekly_days(*, today_weekday: int) -> list[dict]:
    labels = ["一", "二", "三", "四", "五", "六", "日"]
    return [
        {
            "weekday": index,
            "label": label,
            "is_today": index == today_weekday,
            "items": [],
            "hidden_items": [],
            "has_hidden_items": False,
        }
        for index, label in enumerate(labels)
    ]


def _schedule_item(
    *,
    item_id: int,
    title: str,
    poster_url: str | None,
    is_library_ready: bool = False,
    detail: dict | None = None,
) -> dict:
    return {
        "id": item_id,
        "title": title,
        "poster_url": poster_url,
        "is_library_ready": is_library_ready,
        "detail": detail
        or {
            "title_raw": None,
            "group_name": None,
            "source": None,
            "subtitle": None,
            "dpi": None,
            "season_label": None,
            "review_reason": None,
        },
    }


def _script_text(name: str) -> str:
    return (main_module.APP_DIR / "static" / name).read_text(encoding="utf-8")


def _contract_paths(name: str, *, root_var: str = "payload") -> set[str]:
    normalized_paths = set()
    ignored_suffixes = {"length", "map"}
    pattern = rf"{re.escape(root_var)}((?:\??\.[A-Za-z_][A-Za-z0-9_]*)+)"
    for path_suffix in re.findall(pattern, _script_text(name)):
        normalized = path_suffix.replace("?.", ".")
        path = normalized.removeprefix(".")
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
    root_var: str = "payload",
    ignored_paths: set[str] | None = None,
) -> None:
    ignored = ignored_paths or set()
    missing = sorted(
        path
        for path in _contract_paths(script_name, root_var=root_var)
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


def test_overview_payload_matches_phase3_dashboard_app_contract(monkeypatch, tmp_path):
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
            "AUTOBANGUMI_API_URL": "",
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
    weekly_days = _empty_weekly_days(today_weekday=2)
    weekly_days[2] = {
        "weekday": 2,
        "label": "三",
        "is_today": True,
        "items": [_schedule_item(item_id=101, title="示例番剧", poster_url=None)],
        "hidden_items": [
            _schedule_item(
                item_id=102,
                title="隐藏番剧",
                poster_url="http://ops.local:7892/posters/102.jpg",
                is_library_ready=True,
                detail={
                    "title_raw": "Hidden Show",
                    "group_name": "ANi",
                    "source": "Baha",
                    "subtitle": "CHT",
                    "dpi": "1080P",
                    "season_label": "S01",
                    "review_reason": None,
                },
            )
        ],
        "has_hidden_items": True,
    }
    captured_phase4_kwargs: dict[str, object] = {}

    def fake_phase4_snapshot(**kwargs):
        captured_phase4_kwargs.update(kwargs)
        return {
            "today_focus": {"items": [_schedule_item(item_id=101, title="示例番剧", poster_url=None)]},
            "weekly_schedule": {
                "week_key": "2026-W15",
                "today_weekday": 2,
                "days": weekly_days,
                "unknown": {
                    "label": "未知",
                    "hint": "拖拽以设置放送日",
                    "items": [
                        _schedule_item(
                            item_id=201,
                            title="未知排期",
                            poster_url=None,
                            detail={
                                "title_raw": "Unknown Show",
                                "group_name": "喵萌奶茶屋",
                                "source": None,
                                "subtitle": "简日双语",
                                "dpi": "1080P",
                                "season_label": "S01",
                                "review_reason": "季度偏移待确认",
                            },
                        )
                    ],
                    "hidden_items": [_schedule_item(item_id=202, title="未知隐藏", poster_url="http://ops.local:7892/posters/202.jpg")],
                    "has_hidden_items": True,
                },
            },
        }

    monkeypatch.setattr(
        overview_service,
        "build_phase4_schedule_snapshot",
        fake_phase4_snapshot,
        raising=False,
    )

    payload = build_overview_payload()
    app_contract_paths = _contract_paths("app.js", root_var="data")

    assert {
        "hero.title",
        "hero.summary",
        "hero.status_tone",
        "hero.status_label",
        "hero.host",
        "summary_strip",
        "today_focus.items",
        "weekly_schedule.today_weekday",
        "weekly_schedule.days",
        "weekly_schedule.unknown",
        "pipeline_cards",
        "system_cards",
        "network_cards",
        "trend_cards",
        "diagnostics",
    }.issubset(app_contract_paths)
    assert "services" not in app_contract_paths
    assert "queue_cards" not in app_contract_paths
    assert "title" not in app_contract_paths
    assert "subtitle" not in app_contract_paths
    assert "host" not in app_contract_paths
    assert "service_rows" not in app_contract_paths
    assert "stack_control" not in app_contract_paths

    _assert_payload_matches_page_contract(
        payload=payload,
        script_name="app.js",
        root_var="data",
    )
    assert isinstance(payload["hero"], dict)
    assert {"eyebrow", "title", "summary", "status_tone", "status_label", "host"}.issubset(payload["hero"].keys())
    assert isinstance(payload["summary_strip"], list) and payload["summary_strip"]
    assert {"question", "answer", "tone"}.issubset(payload["summary_strip"][0].keys())
    assert isinstance(payload["pipeline_cards"], list) and payload["pipeline_cards"]
    assert {"label", "value", "detail"}.issubset(payload["pipeline_cards"][0].keys())
    assert isinstance(payload["trend_cards"], list) and payload["trend_cards"]
    assert {"label", "value", "detail", "chart_kind"}.issubset(payload["trend_cards"][0].keys())
    assert isinstance(payload["service_rows"], list) and payload["service_rows"]
    assert isinstance(payload["stack_control"], dict)
    assert payload["today_focus"]["items"][0]["is_library_ready"] is False
    assert captured_phase4_kwargs["autobangumi_base_url"] == "http://autobangumi:7892"

    today_focus_item = payload["today_focus"]["items"][0]
    assert {"id", "title", "poster_url", "is_library_ready", "detail"}.issubset(today_focus_item.keys())
    assert {"title_raw", "group_name", "source", "subtitle", "dpi", "season_label", "review_reason"}.issubset(
        today_focus_item["detail"].keys()
    )

    assert len(payload["weekly_schedule"]["days"]) == 7
    today_day = next(day for day in payload["weekly_schedule"]["days"] if day["weekday"] == 2)
    assert {"weekday", "label", "items", "hidden_items", "has_hidden_items"}.issubset(today_day.keys())
    assert {"id", "title", "poster_url", "is_library_ready", "detail"}.issubset(today_day["items"][0].keys())
    assert {"id", "title", "poster_url", "is_library_ready", "detail"}.issubset(today_day["hidden_items"][0].keys())

    assert payload["weekly_schedule"]["unknown"]["label"] == "未知"
    assert {"label", "hint", "items", "hidden_items", "has_hidden_items"}.issubset(payload["weekly_schedule"]["unknown"].keys())
    assert {"id", "title", "poster_url", "is_library_ready", "detail"}.issubset(
        payload["weekly_schedule"]["unknown"]["items"][0].keys()
    )
    assert {"id", "title", "poster_url", "is_library_ready", "detail"}.issubset(
        payload["weekly_schedule"]["unknown"]["hidden_items"][0].keys()
    )


def test_overview_app_script_schedule_contract_reads_nested_fields_and_caps_unknown_bucket():
    script = _script_text("app.js")

    assert "item?.title" in script
    assert "item?.poster_url" in script
    assert "item?.is_library_ready" in script
    assert "item?.detail?.title_raw" in script
    assert "item?.detail?.group_name" in script
    assert "item?.detail?.source" in script
    assert "item?.detail?.subtitle" in script
    assert "item?.detail?.dpi" in script
    assert "item?.detail?.season_label" in script
    assert "item?.detail?.review_reason" in script
    assert "day?.weekday" in script
    assert "day?.label" in script
    assert "day?.items" in script
    assert "day?.hidden_items" in script
    assert "day?.has_hidden_items" in script
    assert "unknown?.label" in script
    assert "unknown?.items" in script
    assert "unknown?.hidden_items" in script
    assert "unknown?.has_hidden_items" in script

    assert "UNKNOWN_VISIBLE_LIMIT" in script
    assert ".slice(0, UNKNOWN_VISIBLE_LIMIT)" in script
    assert ".slice(UNKNOWN_VISIBLE_LIMIT)" in script
    assert "item?.badges" not in script
    assert "ID ${item.id}" not in script


def test_overview_payload_logs_count_uses_uncapped_events_while_phase4_uses_limited_events(monkeypatch):
    monkeypatch.setattr(main_module, "_sample_history_once", lambda: None)
    monkeypatch.setattr(main_module, "_safe_get_json", lambda *args, **kwargs: ({}, None))
    monkeypatch.setattr(main_module, "_tailscale_status", lambda *args, **kwargs: ({}, None))
    monkeypatch.setattr(main_module, "_qb_snapshot", lambda: (None, None))
    monkeypatch.setattr(main_module, "_fan_state_snapshot", lambda: (None, None))
    monkeypatch.setattr(main_module, "_series_values", lambda name, window_hours: ([], []))
    monkeypatch.setattr(main_module, "_daily_volume_bars", lambda *, days, daily_key: ([], []))
    monkeypatch.setattr(main_module, "_count_media_files", lambda root: 0)
    monkeypatch.setattr(main_module, "_count_series_dirs", lambda root: 0)

    phase4_events_count = {"value": None}

    def fake_read_events(*, limit=None):
        count = 300 if limit == 300 else 450
        return [{"id": idx, "ts_unix": idx} for idx in range(count)]

    monkeypatch.setattr(main_module, "read_events", fake_read_events)

    def fake_phase4(**kwargs):
        phase4_events_count["value"] = len(kwargs["events"])
        return {
            "today_focus": {"items": []},
            "weekly_schedule": {
                "week_key": "2026-W15",
                "today_weekday": 2,
                "days": _empty_weekly_days(today_weekday=2),
                "unknown": {
                    "label": "未知",
                    "hint": "拖拽以设置放送日",
                    "items": [],
                    "hidden_items": [],
                    "has_hidden_items": False,
                },
            },
        }

    monkeypatch.setattr(overview_service, "build_phase4_schedule_snapshot", fake_phase4)

    payload = build_overview_payload()

    logs_service = next(item for item in payload["services"] if item["id"] == "logs")
    assert phase4_events_count["value"] == 300
    assert logs_service["meta"] == "450 events"


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


def test_shell_script_contains_left_rail_service_action_handlers():
    script = _script_text("shell.js")

    assert "data-shell-actions" in script
    assert "data-service-action" in script
    assert "data-stack-action" in script
    assert "/api/services/restart" in script
    assert "/api/services/restart-all" in script


def test_shell_script_restores_action_button_markup_after_busy_state():
    if shutil.which("node") is None:
        pytest.skip("node is required for shell.js runtime contract coverage")

    script = _script_text("shell.js")
    runner = """
const vm = require("node:vm");
const script = process.env.SHELL_SCRIPT;

function makeButton() {
  let innerHTML = '<span class="nav-action-icon">J</span><span class="nav-action-copy"><span class="nav-action-title">Restart Jellyfin</span><span class="nav-action-detail">Jellyfin</span></span>';
  let textValue = 'JRestart JellyfinJellyfin';
  return {
    dataset: {},
    disabled: false,
    get innerHTML() {
      return innerHTML;
    },
    set innerHTML(value) {
      innerHTML = String(value);
      textValue = String(value).replace(/<[^>]+>/g, '');
    },
    get textContent() {
      return textValue;
    },
    set textContent(value) {
      innerHTML = String(value);
      textValue = String(value);
    },
  };
}

const context = {
  console,
  document: {
    querySelector() {
      return null;
    },
    getElementById() {
      return null;
    },
  },
  fetch: async () => ({ ok: true, json: async () => ({}) }),
  setTimeout,
  clearTimeout,
  URL,
  window: {
    location: { href: "http://localhost:3000/" },
    setTimeout,
    clearTimeout,
    confirm: () => true,
  },
};

context.globalThis = context;
vm.createContext(context);
vm.runInContext(script, context);

const button = makeButton();
context.setActionButtonBusy(button, true, "Restarting…");
context.setActionButtonBusy(button, false);
process.stdout.write(button.innerHTML);
"""
    env = os.environ.copy()
    env["SHELL_SCRIPT"] = script

    result = subprocess.run(
        ["node", "-e", runner],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert '<span class="nav-action-icon">J</span>' in result.stdout
    assert "nav-action-detail" in result.stdout


def test_shell_script_clears_previous_feedback_timeout():
    if shutil.which("node") is None:
        pytest.skip("node is required for shell.js runtime contract coverage")

    script = _script_text("shell.js")
    runner = """
const vm = require("node:vm");
const script = process.env.SHELL_SCRIPT;

const cleared = [];
let nextId = 1;
const flash = {
  textContent: "",
  className: "inline-feedback is-hidden",
};

const context = {
  console,
  document: {
    querySelector() {
      return null;
    },
    getElementById(id) {
      if (id === "shell-service-feedback") {
        return flash;
      }
      return null;
    },
  },
  fetch: async () => ({ ok: true, json: async () => ({}) }),
  setTimeout,
  clearTimeout,
  URL,
  window: {
    location: { href: "http://localhost:3000/" },
    confirm: () => true,
    setTimeout(callback, delay) {
      const id = nextId++;
      return id;
    },
    clearTimeout(id) {
      cleared.push(id);
    },
  },
};

context.globalThis = context;
vm.createContext(context);
vm.runInContext(script, context);

context.showShellFeedback("success", "one");
context.showShellFeedback("error", "two");
process.stdout.write(JSON.stringify({ cleared, className: flash.className, textContent: flash.textContent }));
"""
    env = os.environ.copy()
    env["SHELL_SCRIPT"] = script

    result = subprocess.run(
        ["node", "-e", runner],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    payload = json.loads(result.stdout)
    assert payload["cleared"] == [1]
    assert payload["className"] == "inline-feedback inline-feedback-error"
    assert payload["textContent"] == "two"


def test_shell_script_normalizes_external_links_to_browser_origin():
    if shutil.which("node") is None:
        pytest.skip("node is required for shell.js runtime contract coverage")

    script = _script_text("shell.js")
    payload = {
        "internal": [],
        "external": [
            {
                "id": "jellyfin",
                "target": "external",
                "href": "http://ops.local:8096",
            },
            {
                "id": "qbittorrent",
                "target": "external",
                "href": "http://ops.local:8080/library?x=1#frag",
            },
        ],
    }
    runner = """
const vm = require("node:vm");
const script = process.env.SHELL_SCRIPT;
const payload = JSON.parse(process.env.SHELL_PAYLOAD);

function makeClassList(initial = []) {
  const classes = new Set(initial);
  return {
    add(...names) {
      for (const name of names) classes.add(name);
    },
    remove(...names) {
      for (const name of names) classes.delete(name);
    },
    toggle(name, force) {
      if (force === true) {
        classes.add(name);
        return true;
      }
      if (force === false) {
        classes.delete(name);
        return false;
      }
      if (classes.has(name)) {
        classes.delete(name);
        return false;
      }
      classes.add(name);
      return true;
    },
    contains(name) {
      return classes.has(name);
    },
    [Symbol.iterator]() {
      return classes.values();
    },
  };
}

function makeLink(id) {
  let href = `http://fallback.invalid/${id}`;
  const attributes = {};
  return {
    dataset: { navItem: id },
    classList: makeClassList(["nav-link"]),
    querySelector() {
      return null;
    },
    removeAttribute(name) {
      delete attributes[name];
    },
    setAttribute(name, value) {
      attributes[name] = String(value);
    },
    getAttribute(name) {
      return attributes[name] ?? null;
    },
    get href() {
      return href;
    },
    set href(value) {
      href = String(value);
    },
  };
}

const links = {
  jellyfin: makeLink("jellyfin"),
  qbittorrent: makeLink("qbittorrent"),
};

const context = {
  console,
  document: {
    body: {
      dataset: {
        navigationApiPath: "/api/navigation",
        page: "dashboard",
      },
    },
    querySelector(selector) {
      if (selector === '[data-shell-nav="external"]') {
        return {
          querySelectorAll() {
            return Object.values(links);
          },
        };
      }
      if (selector === '[data-nav-toggle]') {
        return null;
      }
      return null;
    },
    getElementById() {
      return null;
    },
  },
  fetch: async () => ({
    ok: true,
    json: async () => payload,
  }),
  setTimeout,
  clearTimeout,
  URL,
  window: {
    location: {
      href: "https://tail.example.ts.net:3000/",
    },
    setTimeout,
    clearTimeout,
  },
};

context.globalThis = context;
vm.createContext(context);
vm.runInContext(script, context);

setImmediate(() => {
  process.stdout.write(
    JSON.stringify(Object.values(links).map((link) => link.href))
  );
});
"""
    env = os.environ.copy()
    env["SHELL_SCRIPT"] = script
    env["SHELL_PAYLOAD"] = json.dumps(payload)

    result = subprocess.run(
        ["node", "-e", runner],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    hrefs = json.loads(result.stdout)
    assert hrefs == [
        "https://tail.example.ts.net:8096/",
        "https://tail.example.ts.net:8080/library?x=1#frag",
    ]


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
    _assert_payload_matches_page_contract(
        payload=payload,
        script_name="shell.js",
        ignored_paths={"detail", "message", "reload_after_seconds"},
    )

    assert payload["internal"]
    assert payload["external"]
    assert payload["service_actions"] == SERVICE_ACTIONS
    assert payload["stack_action"] == STACK_ACTION
    assert {item["id"] for item in payload["internal"]} == set(INTERNAL_PAGES.keys())
    assert {item["id"] for item in payload["external"]} == set(EXTERNAL_SERVICES.keys())

    required_internal_keys = {"id", "label", "icon", "target", "path", "href", "badge", "tone"}
    required_external_keys = {"id", "label", "icon", "target", "href", "badge", "tone"}
    assert all(required_internal_keys.issubset(item.keys()) for item in payload["internal"])
    assert all(required_external_keys.issubset(item.keys()) for item in payload["external"])
