from anime_ops_ui.navigation import EXTERNAL_SERVICES, INTERNAL_PAGES
from anime_ops_ui import main as main_module


def test_navigation_registry_contains_expected_groups():
    assert "dashboard" in INTERNAL_PAGES
    assert INTERNAL_PAGES["dashboard"]["path"] == "/"
    assert "ops-review" in INTERNAL_PAGES
    assert INTERNAL_PAGES["ops-review"]["path"] == "/ops-review"
    assert EXTERNAL_SERVICES["jellyfin"]["target"] == "external"
    assert EXTERNAL_SERVICES["qbittorrent"]["port_env"] == "QBITTORRENT_WEBUI_PORT"
    assert EXTERNAL_SERVICES["jellyfin"]["default_port"] == 8096
    assert EXTERNAL_SERVICES["qbittorrent"]["default_port"] == 8080


def test_overview_includes_page_context_fields(client, monkeypatch):
    monkeypatch.setattr(main_module, "_safe_get_json", lambda *args, **kwargs: ({}, None))
    monkeypatch.setattr(main_module, "_tailscale_status", lambda *args, **kwargs: ({}, None))
    monkeypatch.setattr(main_module, "_qb_snapshot", lambda: (None, None))

    response = client.get("/api/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["page_key"] == "dashboard"
    assert payload["page_title"] == "Dashboard"
    assert payload["site_title"] == "RPI Anime Ops"
    assert payload["site_subtitle"] == "树莓派私人影音库控制台"
    assert "ops-review" in payload["internal_pages"]
    assert payload["external_services"]["jellyfin"]["target"] == "external"


def test_navigation_state_service_rolls_up_badges(monkeypatch, tmp_path):
    from anime_ops_ui.services.navigation_state_service import build_navigation_state
    import anime_ops_ui.services.navigation_state_service as navigation_service

    review_root = tmp_path / "manual_review"
    review_root.mkdir(parents=True)
    monkeypatch.setattr(navigation_service, "_NAVIGATION_STATE_FLIGHT", None, raising=False)

    monkeypatch.setattr(main_module, "_manual_review_root", lambda: review_root)
    monkeypatch.setattr(main_module, "_count_media_files", lambda root: 4 if root == review_root else 0)
    monkeypatch.setattr(
        main_module,
        "read_events",
        lambda limit=300: [
            {"level": "error", "message": "boom"},
            {"level": "info", "message": "ok"},
        ],
    )
    monkeypatch.setattr(main_module, "_qb_snapshot", lambda: (_ for _ in ()).throw(AssertionError("live qb probe")))
    monkeypatch.setattr(main_module, "_tailscale_status", lambda socket_path: (_ for _ in ()).throw(AssertionError("live tailscale probe")))
    monkeypatch.setattr(
        main_module,
        "_latest_sampled_metric",
        lambda name: {
            "qb_active_downloads": 3.0,
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
    internal = {item["id"]: item for item in payload["internal"]}
    external = {item["id"]: item for item in payload["external"]}

    assert internal["ops-review"]["badge"] == "4"
    assert internal["ops-review"]["tone"] == "warning"
    assert internal["logs"]["badge"] == "1"
    assert internal["logs"]["tone"] == "danger"
    assert internal["postprocessor"]["badge"] == "3"
    assert internal["postprocessor"]["tone"] == "info"
    assert internal["tailscale"]["badge"] == "Online"
    assert internal["tailscale"]["tone"] == "success"
    assert external["jellyfin"]["href"] == "http://ops.local:8096"
    assert external["jellyfin"]["tone"] == "neutral"
    assert external["jellyfin"]["badge"] is None
    assert set(external.keys()) == {"jellyfin", "qbittorrent", "autobangumi", "glances"}
    assert set(external["jellyfin"].keys()) == {"id", "label", "icon", "target", "href", "badge", "tone"}


def test_navigation_state_service_uses_neutral_state_when_sample_missing(monkeypatch, tmp_path):
    from anime_ops_ui.services.navigation_state_service import build_navigation_state
    import anime_ops_ui.services.navigation_state_service as navigation_service

    review_root = tmp_path / "manual_review"
    review_root.mkdir(parents=True)
    monkeypatch.setattr(navigation_service, "_NAVIGATION_STATE_FLIGHT", None, raising=False)
    monkeypatch.setattr(main_module, "_manual_review_root", lambda: review_root)
    monkeypatch.setattr(main_module, "_count_media_files", lambda root: 0)
    monkeypatch.setattr(main_module, "read_events", lambda limit=300: [])
    monkeypatch.setattr(main_module, "_latest_sampled_metric", lambda name: None)
    monkeypatch.setattr(main_module, "_qb_snapshot", lambda: (_ for _ in ()).throw(AssertionError("live qb probe")))
    monkeypatch.setattr(main_module, "_tailscale_status", lambda socket_path: (_ for _ in ()).throw(AssertionError("live tailscale probe")))

    payload = build_navigation_state()
    internal = {item["id"]: item for item in payload["internal"]}

    assert internal["postprocessor"]["badge"] is None
    assert internal["postprocessor"]["tone"] == "neutral"
    assert internal["tailscale"]["badge"] is None
    assert internal["tailscale"]["tone"] == "neutral"


def test_navigation_state_service_ignores_stale_sampled_badges(monkeypatch, tmp_path):
    from anime_ops_ui.services.navigation_state_service import build_navigation_state
    import anime_ops_ui.services.navigation_state_service as navigation_service

    review_root = tmp_path / "manual_review"
    review_root.mkdir(parents=True)
    stale_ts = 0.0
    monkeypatch.setattr(navigation_service, "_NAVIGATION_STATE_FLIGHT", None, raising=False)
    monkeypatch.setattr(main_module, "_manual_review_root", lambda: review_root)
    monkeypatch.setattr(main_module, "_count_media_files", lambda root: 0)
    monkeypatch.setattr(main_module, "read_events", lambda limit=300: [])
    monkeypatch.setattr(main_module, "_qb_snapshot", lambda: (_ for _ in ()).throw(AssertionError("live qb probe")))
    monkeypatch.setattr(main_module, "_tailscale_status", lambda socket_path: (_ for _ in ()).throw(AssertionError("live tailscale probe")))
    monkeypatch.setattr(
        main_module,
        "HISTORY_STATE",
        {
            "samples": {
                "qb_active_downloads": [{"ts": stale_ts, "value": 3.0}],
                "tailscale_online": [{"ts": stale_ts, "value": 1.0}],
            },
            "download_daily": {},
            "upload_daily": {},
            "last_download_total": None,
            "last_upload_total": None,
            "last_sample_ts": stale_ts,
        },
        raising=False,
    )
    monkeypatch.setattr(main_module, "_env", lambda name, default: {"HOMEPAGE_BASE_HOST": "ops.local"}.get(name, default))

    payload = build_navigation_state()
    internal = {item["id"]: item for item in payload["internal"]}

    assert internal["postprocessor"]["badge"] is None
    assert internal["postprocessor"]["tone"] == "neutral"
    assert internal["tailscale"]["badge"] is None
    assert internal["tailscale"]["tone"] == "neutral"


def test_navigation_state_service_builds_fresh_on_sequential_calls(monkeypatch, tmp_path):
    import anime_ops_ui.services.navigation_state_service as navigation_service

    review_root = tmp_path / "manual_review"
    review_root.mkdir(parents=True)
    calls = {"scan": 0, "events": 0, "metrics": 0}
    monkeypatch.setattr(navigation_service, "_NAVIGATION_STATE_FLIGHT", None, raising=False)

    monkeypatch.setattr(main_module, "_manual_review_root", lambda: review_root)

    def fake_count_media_files(root):
        calls["scan"] += 1
        return calls["scan"] if root == review_root else 0

    monkeypatch.setattr(main_module, "_count_media_files", fake_count_media_files)

    def fake_read_events(limit=300):
        calls["events"] += 1
        return [{"level": "error", "message": "boom"}]

    monkeypatch.setattr(main_module, "read_events", fake_read_events)
    monkeypatch.setattr(main_module, "_qb_snapshot", lambda: (_ for _ in ()).throw(AssertionError("live qb probe")))
    monkeypatch.setattr(main_module, "_tailscale_status", lambda socket_path: (_ for _ in ()).throw(AssertionError("live tailscale probe")))

    def fake_latest_sampled_metric(name):
        calls["metrics"] += 1
        if name == "qb_active_downloads":
            return 2.0
        if name == "tailscale_online":
            return 1.0
        return None

    monkeypatch.setattr(main_module, "_latest_sampled_metric", fake_latest_sampled_metric)
    monkeypatch.setattr(main_module, "_env", lambda name, default: {"HOMEPAGE_BASE_HOST": "ops.local"}.get(name, default))

    first = navigation_service.build_navigation_state()
    second = navigation_service.build_navigation_state()

    first_internal = {item["id"]: item for item in first["internal"]}
    second_internal = {item["id"]: item for item in second["internal"]}
    assert first_internal["ops-review"]["badge"] == "1"
    assert second_internal["ops-review"]["badge"] == "2"
    assert calls == {"scan": 2, "events": 2, "metrics": 4}


def test_navigation_state_service_coalesces_inflight_build(monkeypatch):
    import time
    import threading
    import anime_ops_ui.services.navigation_state_service as navigation_service

    monkeypatch.setattr(navigation_service, "_NAVIGATION_STATE_FLIGHT", None, raising=False)
    started = threading.Event()
    release = threading.Event()
    calls = {"builds": 0}
    payload = {
        "internal": [{"id": "dashboard", "label": "Dashboard", "icon": "D", "target": "internal", "path": "/", "href": "/", "badge": None, "tone": "neutral"}],
        "external": [{"id": "jellyfin", "label": "Jellyfin", "icon": "J", "target": "external", "href": "http://ops.local:8096", "badge": None, "tone": "neutral"}],
    }

    def fake_build_uncached():
        calls["builds"] += 1
        started.set()
        assert release.wait(timeout=1.0)
        return payload

    monkeypatch.setattr(navigation_service, "_build_navigation_state_uncached", fake_build_uncached)

    thread_result = {}
    second_result = {}

    def worker_first():
        thread_result["payload"] = navigation_service.build_navigation_state()

    def worker_second():
        second_result["payload"] = navigation_service.build_navigation_state()

    thread = threading.Thread(target=worker_first)
    thread_2 = threading.Thread(target=worker_second)
    thread.start()
    assert started.wait(timeout=1.0)
    thread_2.start()
    time.sleep(0.05)
    release.set()
    thread.join(timeout=1.0)
    thread_2.join(timeout=1.0)

    assert not thread.is_alive()
    assert not thread_2.is_alive()
    assert calls["builds"] == 1
    assert second_result["payload"] == thread_result["payload"] == payload
