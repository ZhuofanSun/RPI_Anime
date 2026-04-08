from anime_ops_ui.navigation import EXTERNAL_SERVICES, INTERNAL_PAGES
from anime_ops_ui import main as main_module


def test_navigation_registry_contains_expected_groups():
    assert "dashboard" in INTERNAL_PAGES
    assert INTERNAL_PAGES["dashboard"]["path"] == "/"
    assert "ops-review" in INTERNAL_PAGES
    assert INTERNAL_PAGES["ops-review"]["path"] == "/ops-review"
    assert EXTERNAL_SERVICES["jellyfin"]["target"] == "external"
    assert EXTERNAL_SERVICES["qbittorrent"]["port_env"] == "QBITTORRENT_WEBUI_PORT"


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
