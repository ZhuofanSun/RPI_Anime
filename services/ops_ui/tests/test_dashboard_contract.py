from anime_ops_ui import main as main_module
from anime_ops_ui.navigation import EXTERNAL_SERVICES, INTERNAL_PAGES


def test_navigation_api_contract_returns_internal_and_external(client, monkeypatch, tmp_path):
    review_root = tmp_path / "manual_review"
    review_root.mkdir(parents=True)

    monkeypatch.setattr(main_module, "_manual_review_root", lambda: review_root)
    monkeypatch.setattr(main_module, "_count_media_files", lambda root: 2 if root == review_root else 0)
    monkeypatch.setattr(main_module, "read_events", lambda limit=300: [])
    monkeypatch.setattr(main_module, "_qb_snapshot", lambda: (_ for _ in ()).throw(AssertionError("live qb probe")))
    monkeypatch.setattr(main_module, "_tailscale_status", lambda socket_path: (_ for _ in ()).throw(AssertionError("live tailscale probe")))
    monkeypatch.setattr(
        main_module,
        "_latest_sampled_metric",
        lambda name: {
            "qb_active_downloads": 1.0,
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

    response = client.get("/api/navigation")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"internal", "external"}
    dashboard = next(item for item in payload["internal"] if item["id"] == "dashboard")
    jellyfin = next(item for item in payload["external"] if item["id"] == "jellyfin")
    assert dashboard["href"] == "/"
    assert jellyfin["href"] == "http://ops.local:8096"
    assert set(item["id"] for item in payload["internal"]) == set(INTERNAL_PAGES.keys())
    assert set(item["id"] for item in payload["external"]) == set(EXTERNAL_SERVICES.keys())
    assert set(dashboard.keys()) == {"id", "label", "icon", "target", "path", "href", "badge", "tone"}
    assert set(jellyfin.keys()) == {"id", "label", "icon", "target", "href", "badge", "tone"}


def test_overview_api_contract_exposes_phase3_sections(client, monkeypatch):
    monkeypatch.setattr(main_module, "_safe_get_json", lambda *args, **kwargs: ({}, None))
    monkeypatch.setattr(main_module, "_tailscale_status", lambda *args, **kwargs: ({}, None))
    monkeypatch.setattr(main_module, "_qb_snapshot", lambda: (None, None))
    monkeypatch.setattr(main_module, "_fan_state_snapshot", lambda: (None, None))
    monkeypatch.setattr(main_module, "read_events", lambda limit=300: [])

    response = client.get("/api/overview")

    assert response.status_code == 200
    payload = response.json()
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
    assert "services" in payload
    assert "queue_cards" in payload
