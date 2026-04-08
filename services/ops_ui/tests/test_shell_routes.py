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
