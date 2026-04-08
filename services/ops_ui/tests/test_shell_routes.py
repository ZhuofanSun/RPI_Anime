def test_dashboard_uses_shared_shell(client):
    response = client.get("/")
    body = response.text
    assert "app-shell" in body
    assert "Dashboard" in body
    assert "Ops Review" in body
    assert "Jellyfin" in body


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
