from anime_ops_ui.services import mobile_system_service


def test_mobile_system_overview_returns_compact_contract(client, monkeypatch):
    monkeypatch.setattr(
        mobile_system_service,
        "build_overview",
        lambda locale=None: {
            "system_cards": [
                {"label": "CPU 使用", "value": "42%"},
                {"label": "CPU 温度", "value": "58°C"},
                {"label": "内存", "value": "63%"},
                {"label": "主机开机时间", "value": "4 天 03:18"},
                {"label": "服务摘要", "value": "6"},
                {"label": "硬盘", "value": "71%"},
            ],
            "trend_cards": [
                {"label": "24 小时 CPU", "value": "42%", "points": [18.0, 36.0, 42.0]},
                {"label": "24 小时温度", "value": "58°C", "points": [54.0, 56.0, 58.0]},
                {"label": "客户端流量", "value": "3.2 MB/s", "points": [1.2, 2.1, 3.2]},
                {
                    "label": "7 日下载",
                    "value": "5.6 GB",
                    "bars": [
                        {"label": "04-11", "value": 1_024.0, "value_label": "1.0 KB"},
                        {"label": "04-12", "value": 2_048.0, "value_label": "2.0 KB"},
                    ],
                },
            ],
            "last_updated": "2099-01-01T00:00:00Z",
        },
    )
    monkeypatch.setattr(
        mobile_system_service,
        "_fan_value",
        lambda locale=None: "72%",
    )

    response = client.get("/api/mobile/system/overview", headers={"Accept-Language": "zh-Hans"})

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"statusCards", "trends", "supplementary", "updatedAt"}
    assert set(payload["statusCards"]) == {"cpu", "temperature", "memory", "disk"}
    assert payload["statusCards"]["cpu"]["displayValue"] == "42%"
    assert payload["statusCards"]["cpu"]["numericValue"] == 42.0
    assert payload["trends"]["cpu24h"]["points"] == [18.0, 36.0, 42.0]
    assert payload["trends"]["downloads7d"]["bars"][0]["label"] == "04-11"
    assert payload["supplementary"]["fan"] == {"title": "风扇", "value": "72%"}
    assert payload["supplementary"]["uptime"]["value"] == "4 天 03:18"
    assert payload["updatedAt"] == "2099-01-01T00:00:00Z"
