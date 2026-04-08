from anime_ops_ui import main as main_module


def test_navigation_api_contract_returns_internal_and_external(client, monkeypatch, tmp_path):
    review_root = tmp_path / "manual_review"
    review_root.mkdir(parents=True)

    monkeypatch.setattr(main_module, "_manual_review_root", lambda: review_root)
    monkeypatch.setattr(main_module, "_count_media_files", lambda root: 2 if root == review_root else 0)
    monkeypatch.setattr(main_module, "read_events", lambda limit=300: [])
    monkeypatch.setattr(main_module, "_qb_snapshot", lambda: ({"active_downloads": 1}, None))
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

    response = client.get("/api/navigation")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"internal", "external"}
    dashboard = next(item for item in payload["internal"] if item["id"] == "dashboard")
    jellyfin = next(item for item in payload["external"] if item["id"] == "jellyfin")
    assert dashboard["href"] == "/"
    assert jellyfin["href"] == "http://ops.local:8096"
