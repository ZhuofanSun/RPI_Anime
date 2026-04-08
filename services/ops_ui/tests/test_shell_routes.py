def test_internal_pages_render_successfully(client):
    for path in ["/", "/ops-review", "/ops-review/item", "/logs", "/postprocessor", "/tailscale"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


def test_static_assets_render_successfully(client):
    response = client.get("/static/app.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
