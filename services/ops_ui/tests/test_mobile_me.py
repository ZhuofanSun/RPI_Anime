from anime_ops_ui.services import mobile_me_service


def test_mobile_me_context_returns_service_health(client):
    response = client.get("/api/mobile/me/context")

    assert response.status_code == 200
    payload = response.json()
    assert payload["identity"] == {
        "serverLabel": "RPI Anime",
        "connectionState": "online",
    }
    assert set(payload["about"]) == {"backendVersion"}
    assert "serviceHealth" in payload
    assert "maintenance" not in payload
    assert any(item["target"] == "jellyfin" for item in payload["serviceHealth"])


def test_mobile_me_context_uses_real_backend_version_and_localized_homepage_detail(client, monkeypatch):
    monkeypatch.setattr(
        mobile_me_service,
        "build_overview_payload",
        lambda: {
            "service_rows": [
                {
                    "id": "jellyfin",
                    "name": "Jellyfin",
                    "status": "running",
                    "uptime": "2d 4h",
                }
            ]
        },
    )
    monkeypatch.setattr(mobile_me_service, "_backend_version", lambda: "9.9.9")

    zh_response = client.get("/api/mobile/me/context", headers={"Accept-Language": "zh-Hans"})
    en_response = client.get("/api/mobile/me/context", headers={"Accept-Language": "en"})

    assert zh_response.status_code == 200
    assert en_response.status_code == 200

    zh_payload = zh_response.json()
    en_payload = en_response.json()

    assert zh_payload["about"]["backendVersion"] == "9.9.9"
    assert en_payload["about"]["backendVersion"] == "9.9.9"
    assert zh_payload["serviceHealth"][-1] == {
        "target": "homepage",
        "label": "Ops UI",
        "state": "online",
        "detail": "面向 App 的后端",
    }
    assert en_payload["serviceHealth"][-1] == {
        "target": "homepage",
        "label": "Ops UI",
        "state": "online",
        "detail": "app-facing backend",
    }
