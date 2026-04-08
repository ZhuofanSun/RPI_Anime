def test_internal_pages_render_successfully(client):
    for path in ["/", "/ops-review", "/logs", "/postprocessor", "/tailscale"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
