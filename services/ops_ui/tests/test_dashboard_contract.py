from anime_ops_ui import main as main_module
from anime_ops_ui.navigation import EXTERNAL_SERVICES, INTERNAL_PAGES, SERVICE_ACTIONS, STACK_ACTION
from anime_ops_ui.services import overview_service


def _empty_weekly_days(*, today_weekday: int, locale: str = "zh-Hans") -> list[dict]:
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] if locale == "en" else ["一", "二", "三", "四", "五", "六", "日"]
    return [
        {
            "weekday": index,
            "label": label,
            "is_today": index == today_weekday,
            "items": [],
            "hidden_items": [],
            "has_hidden_items": False,
        }
        for index, label in enumerate(labels)
    ]


def test_page_payload_routes_thread_locale_to_services(client, monkeypatch):
    captured: dict[str, str | tuple[str | None, str | None] | None] = {}

    def fake_overview(*, locale=None, public_host=None):
        captured["overview"] = (locale, public_host)
        return {"ok": True}

    def fake_manual_review(*, locale=None):
        captured["manual_review"] = locale
        return {"ok": True}

    def fake_manual_review_item(item_id, *, locale=None):
        captured["manual_review_item"] = locale
        assert item_id == "demo-item"
        return {"ok": True}

    def fake_logs(*, level=None, source=None, search=None, limit=300, locale=None):
        captured["logs"] = locale
        assert level is None
        assert source is None
        assert search is None
        assert limit == 300
        return {"ok": True}

    def fake_postprocessor(*, locale=None):
        captured["postprocessor"] = locale
        return {"ok": True}

    def fake_tailscale(*, locale=None):
        captured["tailscale"] = locale
        return {"ok": True}

    monkeypatch.setattr(main_module, "build_overview_payload_service", fake_overview)
    monkeypatch.setattr(main_module, "build_manual_review_payload_service", fake_manual_review)
    monkeypatch.setattr(main_module, "build_manual_review_item_payload_service", fake_manual_review_item)
    monkeypatch.setattr(main_module, "build_logs_payload_service", fake_logs)
    monkeypatch.setattr(main_module, "build_postprocessor_payload_service", fake_postprocessor)
    monkeypatch.setattr(main_module, "build_tailscale_payload_service", fake_tailscale)

    headers = {"accept-language": "en-US,en;q=0.9", "host": "100.88.77.66:3000"}
    assert client.get("/api/overview", headers=headers).status_code == 200
    assert client.get("/api/manual-review", headers=headers).status_code == 200
    assert client.get("/api/manual-review/item?id=demo-item", headers=headers).status_code == 200
    assert client.get("/api/logs", headers=headers).status_code == 200
    assert client.get("/api/postprocessor", headers=headers).status_code == 200
    assert client.get("/api/tailscale", headers=headers).status_code == 200

    assert captured == {
        "overview": ("en", "100.88.77.66"),
        "manual_review": "en",
        "manual_review_item": "en",
        "logs": "en",
        "postprocessor": "en",
        "tailscale": "en",
    }


def test_overview_route_prefers_forwarded_host_for_public_links(client, monkeypatch):
    captured: dict[str, str | None] = {}

    def fake_overview(*, locale=None, public_host=None):
        captured["locale"] = locale
        captured["public_host"] = public_host
        return {"ok": True}

    monkeypatch.setattr(main_module, "build_overview_payload_service", fake_overview)

    response = client.get(
        "/api/overview",
        headers={
            "accept-language": "en-US,en;q=0.9",
            "host": "internal.local:3000",
            "x-forwarded-host": "100.101.102.103:3000",
        },
    )

    assert response.status_code == 200
    assert captured == {
        "locale": "en",
        "public_host": "100.101.102.103",
    }


def test_navigation_api_contract_returns_internal_external_and_actions(client, monkeypatch, tmp_path):
    review_root = tmp_path / "manual_review"
    review_root.mkdir(parents=True)

    monkeypatch.setattr(main_module, "_manual_review_root", lambda: review_root)
    monkeypatch.setattr(main_module, "_count_media_files", lambda root: 2 if root == review_root else 0)
    monkeypatch.setattr(main_module, "read_events", lambda limit=300: [])
    monkeypatch.setattr(main_module, "_qb_snapshot", lambda: (_ for _ in ()).throw(AssertionError("live qb probe")))
    monkeypatch.setattr(main_module, "_tailscale_status", lambda socket_path: (_ for _ in ()).throw(AssertionError("live tailscale probe")))
    monkeypatch.setattr(
        main_module,
        "_latest_sampled_metric",
        lambda name: {
            "qb_active_downloads": 1.0,
            "tailscale_online": 1.0,
        }.get(name),
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
    assert set(payload.keys()) == {"internal", "external", "service_actions", "stack_action"}
    dashboard = next(item for item in payload["internal"] if item["id"] == "dashboard")
    jellyfin = next(item for item in payload["external"] if item["id"] == "jellyfin")
    homepage = next(item for item in payload["service_actions"] if item["id"] == "homepage")
    assert dashboard["href"] == "/"
    assert jellyfin["href"] == "http://ops.local:8096"
    assert set(item["id"] for item in payload["internal"]) == set(INTERNAL_PAGES.keys())
    assert set(item["id"] for item in payload["external"]) == set(EXTERNAL_SERVICES.keys())
    assert set(item["id"] for item in payload["service_actions"]) == {item["id"] for item in SERVICE_ACTIONS}
    assert set(dashboard.keys()) == {"id", "label", "icon", "target", "path", "href", "badge", "tone"}
    assert set(jellyfin.keys()) == {"id", "label", "icon", "target", "href", "badge", "tone"}
    assert set(homepage.keys()) == {"id", "label", "name", "target", "icon", "requires_reload"}
    assert payload["stack_action"] == STACK_ACTION


def test_navigation_api_localizes_navigation_and_actions_for_english(client, monkeypatch, tmp_path):
    review_root = tmp_path / "manual_review"
    review_root.mkdir(parents=True)

    monkeypatch.setattr(main_module, "_manual_review_root", lambda: review_root)
    monkeypatch.setattr(main_module, "_count_media_files", lambda root: 2 if root == review_root else 0)
    monkeypatch.setattr(main_module, "read_events", lambda limit=300: [])
    monkeypatch.setattr(main_module, "_latest_sampled_metric", lambda name: 1.0 if name == "tailscale_online" else None)
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

    response = client.get("/api/navigation", headers={"accept-language": "en-US,en;q=0.9"})

    assert response.status_code == 200
    payload = response.json()
    dashboard = next(item for item in payload["internal"] if item["id"] == "dashboard")
    logs = next(item for item in payload["internal"] if item["id"] == "logs")
    tailscale = next(item for item in payload["internal"] if item["id"] == "tailscale")
    jellyfin = next(item for item in payload["external"] if item["id"] == "jellyfin")
    homepage = next(item for item in payload["service_actions"] if item["id"] == "homepage")

    assert dashboard["label"] == "Dashboard"
    assert logs["label"] == "Logs"
    assert tailscale["badge"] == "Online"
    assert jellyfin["label"] == "Jellyfin"
    assert homepage["label"] == "Restart Ops UI"
    assert payload["stack_action"] == {
        "label": "Service Actions",
        "hint": "single + stack restart",
        "stack_label": "Restart Stack",
        "stack_detail": "compose only · homepage last",
    }


def test_navigation_api_prefers_cookie_locale_for_zh_hans(client, monkeypatch, tmp_path):
    review_root = tmp_path / "manual_review"
    review_root.mkdir(parents=True)

    monkeypatch.setattr(main_module, "_manual_review_root", lambda: review_root)
    monkeypatch.setattr(main_module, "_count_media_files", lambda root: 2 if root == review_root else 0)
    monkeypatch.setattr(main_module, "read_events", lambda limit=300: [])
    monkeypatch.setattr(main_module, "_latest_sampled_metric", lambda name: 1.0 if name == "tailscale_online" else None)
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

    client.cookies.set("anime-ops-ui-lang", "zh-Hans")
    response = client.get("/api/navigation", headers={"accept-language": "en-US,en;q=0.9"})

    assert response.status_code == 200
    payload = response.json()
    dashboard = next(item for item in payload["internal"] if item["id"] == "dashboard")
    ops_review = next(item for item in payload["internal"] if item["id"] == "ops-review")
    tailscale = next(item for item in payload["internal"] if item["id"] == "tailscale")
    homepage = next(item for item in payload["service_actions"] if item["id"] == "homepage")

    assert dashboard["label"] == "总览"
    assert ops_review["label"] == "审核队列"
    assert tailscale["badge"] == "在线"
    assert homepage["label"] == "重启 Ops UI"
    assert payload["stack_action"] == {
        "label": "服务动作",
        "hint": "单服务 + 整栈重启",
        "stack_label": "重启服务栈",
        "stack_detail": "仅 compose · 最后重启 Ops UI",
    }
    client.cookies.clear()


def test_overview_api_contract_exposes_phase3_sections(client, monkeypatch):
    monkeypatch.setattr(main_module, "_safe_get_json", lambda *args, **kwargs: ({}, None))
    monkeypatch.setattr(main_module, "_tailscale_status", lambda *args, **kwargs: ({}, None))
    monkeypatch.setattr(main_module, "_qb_snapshot", lambda: (None, None))
    monkeypatch.setattr(main_module, "_fan_state_snapshot", lambda: (None, None))
    monkeypatch.setattr(main_module, "read_events", lambda limit=300: [])

    days = _empty_weekly_days(today_weekday=2, locale="en")
    days[0]["items"] = [{"is_library_ready": True}, {"is_library_ready": False}]
    days[1]["hidden_items"] = [{"is_library_ready": True}]
    days[1]["has_hidden_items"] = True

    monkeypatch.setattr(
        overview_service,
        "build_phase4_schedule_snapshot",
        lambda **kwargs: {
            "weekly_schedule": {
                "week_key": "2026-W15",
                "today_weekday": 2,
                "days": days,
                "unknown": {
                    "label": "Unknown",
                    "hint": "Drag to assign a broadcast day",
                    "items": [{"is_library_ready": True}, {"is_library_ready": True}],
                    "hidden_items": [],
                    "has_hidden_items": False,
                },
            }
        },
        raising=False,
    )

    response = client.get("/api/overview", headers={"accept-language": "en-US,en;q=0.9"})

    assert response.status_code == 200
    payload = response.json()
    assert {
        "hero",
        "summary_strip",
        "pipeline_cards",
        "system_cards",
        "network_cards",
        "trend_cards",
        "service_rows",
        "stack_control",
        "diagnostics",
        "last_updated",
    }.issubset(payload.keys())
    assert payload["hero"]["title"] == "RPI Anime Ops"
    assert payload["hero"]["eyebrow"] == "Control surface"
    assert isinstance(payload["summary_strip"], list)
    assert payload["summary_strip"][0]["question"] == "What is worth watching today?"
    assert payload["summary_strip"][0]["answer"] == "4 ready in library"
    assert payload["summary_strip"][1]["question"] == "Is download and library ingest healthy?"
    assert payload["summary_strip"][2]["question"] == "Are device health and remote access stable?"
    assert set(payload["summary_strip"][0].keys()) == {"question", "answer", "tone"}
    assert "services" in payload
    assert "queue_cards" in payload
    assert "today_focus" not in payload
    assert "weekly_schedule" in payload
    assert len(payload["weekly_schedule"]["days"]) == 7
    assert payload["weekly_schedule"]["unknown"]["label"] == "Unknown"


def test_overview_api_contract_phase4_failure_adds_diagnostic_and_fallback_schedule(client, monkeypatch):
    monkeypatch.setattr(main_module, "_safe_get_json", lambda *args, **kwargs: ({}, None))
    monkeypatch.setattr(main_module, "_tailscale_status", lambda *args, **kwargs: ({}, None))
    monkeypatch.setattr(main_module, "_qb_snapshot", lambda: (None, None))
    monkeypatch.setattr(main_module, "_fan_state_snapshot", lambda: (None, None))
    monkeypatch.setattr(main_module, "read_events", lambda limit=300: [])
    monkeypatch.setattr(
        overview_service,
        "build_phase4_schedule_snapshot",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("phase4 unavailable")),
    )

    response = client.get("/api/overview", headers={"accept-language": "en-US,en;q=0.9"})

    assert response.status_code == 200
    payload = response.json()
    assert "today_focus" not in payload
    assert len(payload["weekly_schedule"]["days"]) == 7
    assert [item["weekday"] for item in payload["weekly_schedule"]["days"]] == [0, 1, 2, 3, 4, 5, 6]
    assert payload["weekly_schedule"]["days"][0]["label"] == "Mon"
    assert payload["weekly_schedule"]["unknown"]["label"] == "Unknown"
    assert any(item.get("source") == "phase4-schedule" for item in payload["diagnostics"])
