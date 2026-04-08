from fastapi.testclient import TestClient

from anime_ops_ui import main as main_module
from anime_ops_ui.main import create_app


def test_dashboard_uses_shared_shell(client):
    response = client.get("/")
    body = response.text
    assert "app-shell" in body
    assert "Dashboard" in body
    assert "Ops Review" in body
    assert "Jellyfin" in body


def test_dashboard_shell_contains_bootstrap_roots(client):
    response = client.get("/")
    body = response.text
    assert 'data-page="dashboard"' in body
    assert 'id="services-grid"' in body
    assert 'id="trend-grid"' in body


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
