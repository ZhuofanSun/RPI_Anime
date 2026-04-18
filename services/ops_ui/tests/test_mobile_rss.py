from anime_ops_ui.services import mobile_rss_service


class _FakeAutoBangumiClient:
    def __init__(self) -> None:
        self.enabled_ids: list[int] = []
        self.disabled_ids: list[int] = []
        self.deleted_ids: list[int] = []
        self.subscribed_urls: list[str] = []

    def fetch_rss_sources(self) -> list[dict]:
        return [
            {
                "id": 2,
                "name": "落语朱音",
                "url": "https://mikanani.me/RSS/Bangumi?bangumiId=3908&subgroupid=583",
                "enabled": True,
                "connection_status": "connected",
                "last_checked_at": "2026-04-17 03:00",
            },
            {
                "id": 1,
                "name": "时光代理人",
                "url": "https://mikanani.me/RSS/Bangumi?bangumiId=1234&subgroupid=233",
                "enabled": False,
                "connection_status": "error",
                "last_checked_at": "2026-04-16 19:30",
            },
        ]

    def analyze_rss(self, *, url: str) -> dict:
        return {
            "official_title": "落语朱音",
            "title_raw": "Akanebanashi",
            "poster_link": "/images/posters/akanebanashi.jpg",
            "year": "2025",
            "season": 1,
            "season_raw": "S1",
            "dpi": "1080P",
            "subtitle": "CHT",
            "group_name": "ANi",
        }

    def subscribe_rss(self, *, url: str, bangumi_payload: dict) -> dict:
        self.subscribed_urls.append(url)
        return {"status": True, "msg_zh": "RSS 订阅成功。", "msg_en": "RSS subscribed."}

    def enable_rss(self, *, rss_id: int) -> dict:
        self.enabled_ids.append(rss_id)
        return {"status": True, "msg_zh": "启用 RSS 成功。", "msg_en": "Enabled."}

    def disable_rss(self, *, rss_id: int) -> dict:
        self.disabled_ids.append(rss_id)
        return {"status": True, "msg_zh": "禁用 RSS 成功。", "msg_en": "Disabled."}

    def delete_rss(self, *, rss_id: int) -> dict:
        self.deleted_ids.append(rss_id)
        return {"msg_zh": "删除 RSS 成功。", "msg_en": "Deleted."}


def test_mobile_rss_list_returns_simplified_contract(client, monkeypatch):
    monkeypatch.setattr(
        mobile_rss_service,
        "_autobangumi_client",
        lambda: _FakeAutoBangumiClient(),
    )
    monkeypatch.setattr(
        mobile_rss_service,
        "_system_timestamp",
        lambda: "2099-01-01T00:00:00Z",
    )

    response = client.get("/api/mobile/rss", headers={"Accept-Language": "zh-Hans"})

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"items", "updatedAt"}
    assert [item["rssId"] for item in payload["items"]] == [2, 1]
    assert payload["items"][0] == {
        "rssId": 2,
        "title": "落语朱音",
        "connectionState": "connected",
        "connectionStateLabel": "已连接",
        "enabled": True,
        "enabledStateLabel": "启用",
        "lastCheckedLabel": "2026-04-17 03:00",
    }
    assert "url" not in payload["items"][0]
    assert payload["updatedAt"] == "2099-01-01T00:00:00Z"


def test_mobile_rss_analyze_returns_preview_and_duplicate_flag(client, monkeypatch):
    monkeypatch.setattr(
        mobile_rss_service,
        "_autobangumi_client",
        lambda: _FakeAutoBangumiClient(),
    )

    response = client.post(
        "/api/mobile/rss/analyze",
        json={"url": "https://mikanani.me/RSS/Bangumi?bangumiId=3908&subgroupid=583"},
        headers={"Accept-Language": "zh-Hans"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["duplicate"] is True
    assert payload["duplicateRssId"] == 2
    assert payload["preview"] == {
        "title": "落语朱音",
        "originalTitle": "Akanebanashi",
        "posterUrl": "http://testserver:7892/images/posters/akanebanashi.jpg",
        "year": "2025",
        "season": "S1",
        "tags": ["1080P", "CHT", "ANi"],
    }
    assert "url" in payload


def test_mobile_rss_subscribe_short_circuits_duplicate(client, monkeypatch):
    fake_client = _FakeAutoBangumiClient()
    monkeypatch.setattr(
        mobile_rss_service,
        "_autobangumi_client",
        lambda: fake_client,
    )

    response = client.post(
        "/api/mobile/rss/subscribe",
        json={"url": "https://mikanani.me/RSS/Bangumi?bangumiId=3908&subgroupid=583"},
        headers={"Accept-Language": "zh-Hans"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "ok": False,
        "duplicate": True,
        "rssId": 2,
        "message": "RSS 源已存在。",
    }
    assert fake_client.subscribed_urls == []


def test_mobile_rss_actions_return_compact_action_payloads(client, monkeypatch):
    fake_client = _FakeAutoBangumiClient()
    monkeypatch.setattr(
        mobile_rss_service,
        "_autobangumi_client",
        lambda: fake_client,
    )

    enable_response = client.post("/api/mobile/rss/2/enable", headers={"Accept-Language": "zh-Hans"})
    disable_response = client.patch("/api/mobile/rss/2/disable", headers={"Accept-Language": "zh-Hans"})
    delete_response = client.delete("/api/mobile/rss/2", headers={"Accept-Language": "zh-Hans"})

    assert enable_response.status_code == 200
    assert enable_response.json() == {
        "ok": True,
        "action": "enable",
        "rssId": 2,
        "message": "启用 RSS 成功。",
    }
    assert disable_response.status_code == 200
    assert disable_response.json() == {
        "ok": True,
        "action": "disable",
        "rssId": 2,
        "message": "禁用 RSS 成功。",
    }
    assert delete_response.status_code == 200
    assert delete_response.json() == {
        "ok": True,
        "action": "delete",
        "rssId": 2,
        "message": "删除 RSS 成功。",
    }
    assert fake_client.enabled_ids == [2]
    assert fake_client.disabled_ids == [2]
    assert fake_client.deleted_ids == [2]
