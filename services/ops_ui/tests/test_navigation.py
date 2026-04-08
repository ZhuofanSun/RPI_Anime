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

    review_root = tmp_path / "manual_review"
    review_root.mkdir(parents=True)

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
    monkeypatch.setattr(main_module, "_qb_snapshot", lambda: ({"active_downloads": 3}, None))
    monkeypatch.setattr(
        main_module,
        "_tailscale_status",
        lambda socket_path: ({"BackendState": "Running", "Self": {"Online": True}}, None),
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


def test_navigation_state_service_reuses_cache_within_ttl(monkeypatch, tmp_path):
    import anime_ops_ui.services.navigation_state_service as navigation_service

    review_root = tmp_path / "manual_review"
    review_root.mkdir(parents=True)
    calls = {"scan": 0, "events": 0, "qb": 0, "tailscale": 0}

    ticks = iter([10.0, 10.05, 10.1])
    monkeypatch.setattr(navigation_service, "_monotonic", lambda: next(ticks), raising=False)
    monkeypatch.setattr(navigation_service, "NAVIGATION_STATE_TTL_SECONDS", 0.25, raising=False)
    monkeypatch.setattr(navigation_service, "_NAVIGATION_STATE_CACHE", None, raising=False)
    monkeypatch.setattr(navigation_service, "_NAVIGATION_STATE_CACHE_TS", 0.0, raising=False)

    monkeypatch.setattr(main_module, "_manual_review_root", lambda: review_root)

    def fake_count_media_files(root):
        calls["scan"] += 1
        return 1 if root == review_root else 0

    monkeypatch.setattr(main_module, "_count_media_files", fake_count_media_files)

    def fake_read_events(limit=300):
        calls["events"] += 1
        return [{"level": "error", "message": "boom"}]

    monkeypatch.setattr(main_module, "read_events", fake_read_events)

    def fake_qb_snapshot():
        calls["qb"] += 1
        return {"active_downloads": 2}, None

    monkeypatch.setattr(main_module, "_qb_snapshot", fake_qb_snapshot)

    def fake_tailscale_status(socket_path):
        calls["tailscale"] += 1
        return {"BackendState": "Running", "Self": {"Online": True}}, None

    monkeypatch.setattr(main_module, "_tailscale_status", fake_tailscale_status)
    monkeypatch.setattr(main_module, "_env", lambda name, default: {"HOMEPAGE_BASE_HOST": "ops.local"}.get(name, default))

    first = navigation_service.build_navigation_state()
    second = navigation_service.build_navigation_state()

    assert first == second
    assert calls == {"scan": 1, "events": 1, "qb": 1, "tailscale": 1}
