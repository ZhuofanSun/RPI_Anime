from anime_ops_ui.navigation import EXTERNAL_SERVICES, INTERNAL_PAGES


def test_navigation_registry_contains_expected_groups():
    assert "dashboard" in INTERNAL_PAGES
    assert INTERNAL_PAGES["dashboard"]["path"] == "/"
    assert EXTERNAL_SERVICES["jellyfin"]["target"] == "external"
    assert EXTERNAL_SERVICES["qbittorrent"]["port_env"] == "QBITTORRENT_WEBUI_PORT"
