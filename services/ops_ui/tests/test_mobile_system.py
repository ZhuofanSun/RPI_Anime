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


def test_mobile_system_downloads_returns_compact_contract(client, monkeypatch):
    monkeypatch.setattr(
        mobile_system_service,
        "_fetch_qbittorrent_downloads",
        lambda: [
            {
                "hash": "torrent_hash_001",
                "name": "[ANi] 灵笼 - 16",
                "size": 1_073_741_824,
                "completed": 858_993_459,
                "progress": 0.8,
                "dlspeed": 3_145_728,
                "state": "downloading",
                "added_on": 1_713_312_000,
            },
            {
                "hash": "torrent_hash_002",
                "name": "[ANi] 凡人修仙传 - 176",
                "size": 734_003_200,
                "completed": 734_003_200,
                "progress": 1.0,
                "dlspeed": 0,
                "state": "uploading",
                "added_on": 1_713_311_000,
            },
        ],
    )
    monkeypatch.setattr(
        mobile_system_service,
        "_system_timestamp",
        lambda: "2099-01-01T00:00:00Z",
    )

    response = client.get("/api/mobile/system/downloads", headers={"Accept-Language": "zh-Hans"})

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"items", "updatedAt"}
    assert len(payload["items"]) == 2
    assert payload["items"][0]["state"] == "downloading"
    assert payload["items"][0]["downloadedBytes"] == 858_993_459
    assert payload["items"][1]["state"] == "completed"
    assert payload["items"][1]["downloadSpeedBytesPerSec"] == 0
    assert payload["items"][1]["progress"] == 1.0
    assert payload["updatedAt"] == "2099-01-01T00:00:00Z"


def test_mobile_system_logs_returns_compact_contract(client, monkeypatch):
    monkeypatch.setattr(
        mobile_system_service,
        "build_logs_payload_service",
        lambda source=None, limit=30, locale=None: {
            "items": [
                {
                    "id": "log_001",
                    "ts": "2099-01-01T00:00:00Z",
                    "source": "autobangumi",
                    "level": "warning",
                    "message": "RSS 刷新超时，等待下次重试",
                },
                {
                    "id": "log_002",
                    "ts": "2098-12-31T23:59:00Z",
                    "source": "qbittorrent",
                    "level": "error",
                    "message": "下载任务失败，等待重新连接",
                },
            ],
            "sources": ["autobangumi", "qbittorrent"],
            "last_updated": "2099-01-01T00:00:30Z",
        },
    )

    response = client.get("/api/mobile/system/logs", headers={"Accept-Language": "zh-Hans"})

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"items", "updatedAt"}
    assert len(payload["items"]) == 2
    assert payload["items"][0]["service"] == "AutoBangumi"
    assert payload["items"][0]["level"] == "warning"
    assert payload["items"][1]["service"] == "qBittorrent"
    assert payload["updatedAt"] == "2099-01-01T00:00:30Z"


def test_mobile_system_tailscale_returns_compact_contract(client, monkeypatch):
    monkeypatch.setattr(
        mobile_system_service,
        "build_tailscale_payload_service",
        lambda locale=None: {
            "current_node": {
                "host": "rpi-anime-app",
                "dns_name": "rpi-anime-app.tailnet.ts.net",
                "ipv4": "100.87.23.14",
                "reachable": True,
            },
            "peers": [
                {
                    "host_name": "ipad",
                    "dns_name": "ipad.tailnet.ts.net",
                    "ip": "100.73.42.77",
                    "status": "offline",
                },
                {
                    "host_name": "iphone",
                    "dns_name": "iphone.tailnet.ts.net",
                    "ip": "100.91.8.23",
                    "status": "online",
                },
                {
                    "host_name": "macbook",
                    "dns_name": "macbook.tailnet.ts.net",
                    "ip": "100.88.11.6",
                    "status": "online",
                },
            ],
        },
    )

    response = client.get("/api/mobile/system/tailscale", headers={"Accept-Language": "zh-Hans"})

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"localNode", "peers"}
    assert payload["localNode"] == {
        "name": "rpi-anime-app",
        "host": "rpi-anime-app.tailnet.ts.net",
        "ipv4": "100.87.23.14",
        "online": True,
    }
    assert [item["name"] for item in payload["peers"]] == ["iphone", "macbook", "ipad"]
    assert payload["peers"][2]["online"] is False
