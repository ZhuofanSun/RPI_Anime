import re

from fastapi.testclient import TestClient

from anime_ops_ui import main as main_module
from anime_ops_ui.i18n import LANGUAGE_COOKIE_NAME
from anime_ops_ui.main import create_app


def test_dashboard_uses_shared_shell(client):
    response = client.get("/")
    body = response.text
    assert "app-shell" in body
    assert "Dashboard" in body
    assert "审核队列" in body
    assert "Jellyfin" in body


def test_shared_shell_localizes_english_shell_markup_and_bootstrap_copy(client):
    response = client.get("/", headers={"accept-language": "en-US,en;q=0.9"})

    assert response.status_code == 200
    body = response.text
    assert '<html lang="en">' in body
    assert 'data-locale="en"' in body
    assert 'data-language-cookie-name="anime-ops-ui-lang"' in body
    assert 'id="ops-ui-client-copy"' in body
    assert '/static/language.js' in body
    assert "Navigation" in body
    assert "Workspace" in body
    assert "Services" in body
    assert "Controls" in body
    assert "Preferences" in body
    assert 'data-preferences-controls' in body
    assert 'data-theme-option="light"' in body
    assert 'data-theme-option="dark"' in body
    assert 'data-language-option="zh-Hans"' in body
    assert 'data-language-option="en"' in body
    assert "theme-toggle-track" not in body
    assert "theme-toggle-icon" not in body
    assert "☀" not in body
    assert "☾" not in body


def test_shared_shell_prefers_cookie_locale_over_accept_language(client):
    client.cookies.set(LANGUAGE_COOKIE_NAME, "en")
    response = client.get("/", headers={"accept-language": "zh-Hans,zh;q=0.9"})

    assert response.status_code == 200
    assert '<html lang="en">' in response.text
    client.cookies.clear()


def test_all_shell_pages_render_shared_preferences_once(client):
    for path in ["/", "/ops-review", "/ops-review/item", "/logs", "/postprocessor", "/tailscale"]:
        response = client.get(path)
        body = response.text
        assert response.status_code == 200
        assert body.count("data-preferences-controls") == 1
        assert "theme-toggle-track" not in body
        assert "theme-toggle-icon" not in body
        assert "☀" not in body
        assert "☾" not in body


def test_dashboard_shell_contains_bootstrap_roots(client):
    response = client.get("/")
    body = response.text
    assert 'data-page="dashboard"' in body
    assert 'id="dashboard-hero"' in body
    assert 'id="dashboard-summary-strip"' in body
    assert 'id="dashboard-today-focus"' not in body
    assert 'id="dashboard-weekly-schedule"' in body
    assert 'id="dashboard-unknown-schedule"' in body
    assert "broadcast-wall" in body
    assert 'id="dashboard-pipeline-grid"' in body
    assert 'id="dashboard-status-grid"' in body
    assert 'id="dashboard-trend-grid"' in body
    assert 'id="services-grid"' not in body
    assert 'id="dashboard-service-rows"' not in body
    assert 'id="restart-stack-button"' not in body


def test_dashboard_shell_contains_navigation_hydration_hooks(client):
    response = client.get("/")
    body = response.text
    assert 'data-navigation-api-path="/api/navigation"' in body
    assert 'data-shell-nav="internal"' in body
    assert 'data-shell-nav="external"' in body
    assert "data-nav-item" in body
    assert "data-nav-badge" in body
    assert "data-nav-toggle" in body
    assert 'aria-controls="shell-nav-sections"' in body
    assert 'id="shell-nav-sections"' in body
    assert "data-shell-actions" in body
    assert 'data-service-action="jellyfin"' in body
    assert 'data-service-action="homepage"' in body
    assert "data-stack-action" in body
    assert '/static/shell.js' in body


def test_dashboard_shell_removes_service_console_panel(client):
    response = client.get("/")
    body = response.text
    assert "Service Console" not in body
    assert "dashboard-services-panel" not in body
    assert "service-panel-feedback" not in body
    assert "dashboard-service-rows" not in body
    assert "restart-stack-button" not in body


def test_external_nav_links_have_server_rendered_fallback_hrefs(client):
    response = client.get("/")
    body = response.text
    assert 'data-shell-nav="external"' in body
    assert re.search(r'data-shell-nav="external"', body)
    assert re.search(r'<a class="nav-link is-external" href="http://[^"]+" data-nav-item="jellyfin"', body)
    assert re.search(r'<a class="nav-link is-external" href="http://[^"]+" data-nav-item="qbittorrent"', body)
    assert re.search(r'<a class="nav-link is-external" href="http://[^"]+" data-nav-item="autobangumi"', body)
    assert re.search(r'<a class="nav-link is-external" href="http://[^"]+" data-nav-item="glances"', body)
    assert re.search(r'<a class="nav-link is-external" href="#" data-nav-item=', body) is None


def test_ops_review_detail_page_keeps_ops_review_nav_active_in_shell_markup(client):
    response = client.get("/ops-review/item")
    body = response.text
    assert 'data-page="ops-review"' in body
    assert re.search(r'class="nav-link is-active"\s+href="/ops-review"\s+data-nav-item="ops-review"', body)


def test_internal_pages_render_successfully(client):
    for path in ["/", "/ops-review", "/ops-review/item", "/logs", "/postprocessor", "/tailscale"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    test_paths = client.app.state.test_paths
    assert not (test_paths["state_root"] / "history.json").exists()
    assert not test_paths["event_log_path"].exists()


def test_static_assets_render_successfully(client):
    response = client.get("/static/app.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]

    test_paths = client.app.state.test_paths
    assert not (test_paths["state_root"] / "history.json").exists()
    assert not test_paths["event_log_path"].exists()


def test_internal_pages_render_single_main_landmark(client):
    for path in ["/", "/ops-review", "/ops-review/item", "/logs", "/postprocessor", "/tailscale"]:
        response = client.get(path)
        body = response.text
        assert body.count("<main") == 1
        assert 'class="app-main"' in body


def test_dashboard_restores_pre_paint_theme_bootstrap(client):
    response = client.get("/")
    body = response.text
    assert 'const key = "anime-ops-ui-theme";' in body
    assert body.index('const key = "anime-ops-ui-theme";') < body.index('<link rel="stylesheet"')


def test_legacy_static_html_pages_are_not_served(client):
    for path in [
        "/static/index.html",
        "/static/ops-review.html",
        "/static/ops-review-item.html",
        "/static/logs.html",
        "/static/postprocessor.html",
        "/static/tailscale.html",
    ]:
        response = client.get(path)
        assert response.status_code == 404


def test_manual_review_item_missing_returns_404(client):
    response = client.get("/api/manual-review/item?id=missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "manual review file not found"


def test_app_factory_default_lifespan_runs_startup(tmp_path, monkeypatch):
    data_root = tmp_path / "anime-data"
    state_root = tmp_path / "ops-ui-state"
    event_log_path = tmp_path / "events.json"
    monkeypatch.setenv("ANIME_DATA_ROOT", str(data_root))
    monkeypatch.setenv("OPS_UI_STATE_ROOT", str(state_root))
    monkeypatch.setenv("OPS_EVENT_LOG_PATH", str(event_log_path))
    main_module.HISTORY_STATE = None

    with TestClient(create_app()) as test_client:
        response = test_client.get("/healthz")
        assert response.status_code == 200

    assert (state_root / "history.json").exists()
    assert event_log_path.exists()
