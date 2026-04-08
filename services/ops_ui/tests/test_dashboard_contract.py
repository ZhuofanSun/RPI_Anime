from anime_ops_ui import main as main_module
from anime_ops_ui.navigation import EXTERNAL_SERVICES, INTERNAL_PAGES, SERVICE_ACTIONS, STACK_ACTION
from anime_ops_ui.services import overview_service


def _empty_weekly_days(*, today_weekday: int) -> list[dict]:
    labels = ["一", "二", "三", "四", "五", "六", "日"]
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


def test_overview_api_contract_exposes_phase3_sections(client, monkeypatch):
    monkeypatch.setattr(main_module, "_safe_get_json", lambda *args, **kwargs: ({}, None))
    monkeypatch.setattr(main_module, "_tailscale_status", lambda *args, **kwargs: ({}, None))
    monkeypatch.setattr(main_module, "_qb_snapshot", lambda: (None, None))
    monkeypatch.setattr(main_module, "_fan_state_snapshot", lambda: (None, None))
    monkeypatch.setattr(main_module, "read_events", lambda limit=300: [])
    monkeypatch.setattr(
        overview_service,
        "build_phase4_schedule_snapshot",
        lambda **kwargs: {
            "today_focus": {
                "items": [
                    {
                        "id": 101,
                        "title": "示例番剧",
                        "poster_url": None,
                        "is_library_ready": True,
                        "detail": {
                            "title_raw": "Sample Show",
                            "group_name": "ANi",
                            "source": "Baha",
                            "subtitle": "CHT",
                            "dpi": "1080P",
                            "season_label": "S01",
                            "review_reason": None,
                        },
                    }
                ]
            },
            "weekly_schedule": {
                "week_key": "2026-W15",
                "today_weekday": 2,
                "days": _empty_weekly_days(today_weekday=2),
                "unknown": {
                    "label": "未知",
                    "hint": "拖拽以设置放送日",
                    "items": [],
                    "hidden_items": [],
                    "has_hidden_items": False,
                },
            },
        },
        raising=False,
    )

    response = client.get("/api/overview")

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
    assert payload["hero"]["eyebrow"] == "Control Surface"
    assert isinstance(payload["summary_strip"], list)
    assert payload["summary_strip"][0]["question"] == "今天有什么值得看"
    assert payload["summary_strip"][1]["question"] == "下载和入库链路是否正常"
    assert payload["summary_strip"][2]["question"] == "设备和远程访问是否健康"
    assert set(payload["summary_strip"][0].keys()) == {"question", "answer", "tone"}
    assert "services" in payload
    assert "queue_cards" in payload
    assert "today_focus" in payload
    assert "weekly_schedule" in payload
    assert len(payload["weekly_schedule"]["days"]) == 7
    assert payload["weekly_schedule"]["unknown"]["label"] == "未知"


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

    response = client.get("/api/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["today_focus"]["items"] == []
    assert len(payload["weekly_schedule"]["days"]) == 7
    assert [item["weekday"] for item in payload["weekly_schedule"]["days"]] == [0, 1, 2, 3, 4, 5, 6]
    assert any(item.get("source") == "phase4-schedule" for item in payload["diagnostics"])
