from anime_ops_ui.services import mobile_me_service


def test_mobile_me_context_returns_service_health(client):
    response = client.get("/api/mobile/me/context")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload["identity"]) == {"serverLabel", "connectionState"}
    assert payload["identity"]["connectionState"] == "online"
    assert payload["identity"]["serverLabel"]
    assert set(payload["about"]) == {"backendVersion"}
    assert "serviceHealth" in payload
    assert "maintenance" not in payload
    assert any(item["target"] == "jellyfin" for item in payload["serviceHealth"])


def test_mobile_me_context_uses_real_backend_version_and_localized_homepage_detail(client, monkeypatch):
    monkeypatch.setattr(
        mobile_me_service,
        "build_overview_payload",
        lambda public_host=None: {
            "host": public_host or "100.123.232.73",
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

    zh_response = client.get("/api/mobile/me/context", headers={"Accept-Language": "zh-Hans", "host": "100.123.232.73:3000"})
    en_response = client.get("/api/mobile/me/context", headers={"Accept-Language": "en", "host": "100.123.232.73:3000"})

    assert zh_response.status_code == 200
    assert en_response.status_code == 200

    zh_payload = zh_response.json()
    en_payload = en_response.json()

    assert zh_payload["about"]["backendVersion"] == "9.9.9"
    assert en_payload["about"]["backendVersion"] == "9.9.9"
    assert zh_payload["identity"] == {
        "serverLabel": "100.123.232.73",
        "connectionState": "online",
    }
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


def test_mobile_me_context_marks_homepage_offline_when_overview_unavailable(client, monkeypatch):
    monkeypatch.setattr(
        mobile_me_service,
        "build_overview_payload",
        lambda public_host=None: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    response = client.get("/api/mobile/me/context", headers={"Accept-Language": "en"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["identity"] == {
        "serverLabel": "RPI Anime",
        "connectionState": "offline",
    }
    assert payload["serviceHealth"][-1] == {
        "target": "homepage",
        "label": "Ops UI",
        "state": "offline",
        "detail": "backend unavailable",
    }
