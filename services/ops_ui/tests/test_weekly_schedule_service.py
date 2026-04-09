import json
import inspect
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from anime_ops_ui.services import weekly_schedule_service as service
from anime_ops_ui.services.weekly_schedule_service import (
    build_phase4_schedule_snapshot,
    build_weekly_schedule_payload,
)


def test_weekly_schedule_groups_items_today_unknown_with_library_highlight_and_tooltip_detail(tmp_path):
    now = datetime(2026, 4, 8, 9, 0, tzinfo=ZoneInfo("America/Toronto"))
    payload = build_weekly_schedule_payload(
        bangumi_items=[
            {
                "id": 9,
                "official_title": "尖帽子的魔法工房",
                "title_raw": "Witch Hat Atelier",
                "air_weekday": now.weekday(),
                "poster_link": "posters/5cac94c7.jpg",
                "needs_review": False,
                "group_name": "ANi",
                "source": "Baha",
                "subtitle": "CHT",
                "dpi": "1080P",
                "season": 1,
                "season_raw": "S01",
            },
            {
                "id": 11,
                "official_title": "相反的你和我",
                "title_raw": "Seihantai na Kimi to Boku",
                "air_weekday": now.weekday(),
                "poster_link": "posters/8d4ed23c.jpg",
                "needs_review": False,
                "group_name": "喵萌奶茶屋",
                "source": None,
                "subtitle": "简日双语",
                "dpi": "1080P",
                "season": 1,
                "season_raw": "",
            },
            {
                "id": 4,
                "official_title": "关于我转生变成史莱姆这档事",
                "air_weekday": None,
                "poster_link": "posters/6b0a8a03.jpg",
                "needs_review": True,
                "needs_review_reason": "季度偏移待确认",
                "group_name": "ANi",
                "source": "Baha",
                "subtitle": "CHT",
                "dpi": "1080P",
                "season": 4,
                "season_raw": "第四季",
            },
        ],
        base_host="sunzhuofan.local",
        autobangumi_port=7892,
        library_ids={9},
        now=now,
        state_root=tmp_path,
        visible_limit=1,
        locale="en",
    )

    assert payload["today_weekday"] == now.weekday()
    assert [item["label"] for item in payload["days"]] == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    assert len(payload["days"]) == 7

    today = payload["days"][now.weekday()]
    assert today["is_today"] is True
    assert today["items"][0]["poster_url"] == "http://sunzhuofan.local:7892/posters/5cac94c7.jpg"
    assert today["items"][0]["is_library_ready"] is True
    assert today["items"][0]["detail"] == {
        "title_raw": "Witch Hat Atelier",
        "group_name": "ANi",
        "source": "Baha",
        "subtitle": "CHT",
        "dpi": "1080P",
        "season_label": "S01",
        "review_reason": None,
    }
    assert today["has_hidden_items"] is True
    assert today["hidden_items"][0]["title"] == "相反的你和我"
    assert today["hidden_items"][0]["is_library_ready"] is False

    assert payload["unknown"]["label"] == "Unknown"
    assert payload["unknown"]["hint"] == "Drag to assign a broadcast day"
    assert payload["unknown"]["items"][0]["title"] == "关于我转生变成史莱姆这档事"
    assert payload["unknown"]["items"][0]["is_library_ready"] is False
    assert payload["unknown"]["items"][0]["detail"]["review_reason"] == "季度偏移待确认"

    state = json.loads((tmp_path / "weekly_schedule_state.json").read_text(encoding="utf-8"))
    assert state["week_key"] == payload["week_key"]


def test_weekly_schedule_localizes_missing_title_fallback(tmp_path):
    now = datetime(2026, 4, 8, 9, 0, tzinfo=ZoneInfo("America/Toronto"))

    zh_payload = build_weekly_schedule_payload(
        bangumi_items=[{"id": 41, "air_weekday": now.weekday(), "poster_link": None}],
        base_host="sunzhuofan.local",
        autobangumi_port=7892,
        library_ids=set(),
        now=now,
        state_root=tmp_path / "zh",
        locale="zh-Hans",
    )
    en_payload = build_weekly_schedule_payload(
        bangumi_items=[{"id": 42, "air_weekday": now.weekday(), "poster_link": None}],
        base_host="sunzhuofan.local",
        autobangumi_port=7892,
        library_ids=set(),
        now=now,
        state_root=tmp_path / "en",
        locale="en",
    )

    assert zh_payload["days"][now.weekday()]["items"][0]["title"] == "未知"
    assert en_payload["days"][now.weekday()]["items"][0]["title"] == "Unknown"


def test_weekly_schedule_rewrites_state_when_iso_week_changes(tmp_path):
    first = build_weekly_schedule_payload(
        bangumi_items=[],
        base_host="sunzhuofan.local",
        autobangumi_port=7892,
        library_ids=set(),
        now=datetime(2026, 4, 8, 9, 0, tzinfo=ZoneInfo("America/Toronto")),
        state_root=tmp_path,
        locale="en",
    )
    first_state = json.loads((tmp_path / "weekly_schedule_state.json").read_text(encoding="utf-8"))

    second = build_weekly_schedule_payload(
        bangumi_items=[],
        base_host="sunzhuofan.local",
        autobangumi_port=7892,
        library_ids=set(),
        now=datetime(2026, 4, 13, 9, 0, tzinfo=ZoneInfo("America/Toronto")),
        state_root=tmp_path,
        locale="en",
    )
    second_state = json.loads((tmp_path / "weekly_schedule_state.json").read_text(encoding="utf-8"))

    assert first["week_key"] != second["week_key"]
    assert first_state["week_key"] == first["week_key"]
    assert second_state["week_key"] == second["week_key"]


def test_phase4_snapshot_derives_library_highlight_from_publish_events(tmp_path, monkeypatch):
    title_map_path = tmp_path / "title_mappings.toml"
    title_map_path.write_text(
        """
[[series]]
folder_name = "Witch Hat Atelier"
series_title = "Witch Hat Atelier"
aliases = ["尖帽子的魔法工房"]
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("POSTPROCESSOR_TITLE_MAP", str(title_map_path))

    now = datetime(2026, 4, 8, 9, 0, tzinfo=ZoneInfo("America/Toronto"))

    class _FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def fetch_bangumi(self):
            return [
                {
                    "id": 9,
                    "official_title": "尖帽子的魔法工房",
                    "title_raw": "Witch Hat Atelier",
                    "air_weekday": now.weekday(),
                    "poster_link": "posters/5cac94c7.jpg",
                    "needs_review": False,
                    "deleted": False,
                    "archived": False,
                },
                {
                    "id": 91,
                    "official_title": "归档条目",
                    "air_weekday": now.weekday(),
                    "poster_link": "posters/archived.jpg",
                    "needs_review": False,
                    "deleted": False,
                    "archived": True,
                },
                {
                    "id": 92,
                    "official_title": "删除条目",
                    "air_weekday": now.weekday(),
                    "poster_link": "posters/deleted.jpg",
                    "needs_review": False,
                    "deleted": True,
                    "archived": False,
                },
            ]

    monkeypatch.setattr(service, "AutoBangumiClient", _FakeClient)

    payload = build_phase4_schedule_snapshot(
        anime_data_root=tmp_path,
        base_host="sunzhuofan.local",
        autobangumi_port=7892,
        autobangumi_base_url="http://sunzhuofan.local:7892",
        autobangumi_username="sunzhuofan",
        autobangumi_password="root1234",
        state_root=tmp_path / "ops-ui-state",
        now=now,
        events=[
            {
                "source": "postprocessor",
                "action": "watch-process-group",
                "message": "this message should not drive matching",
                "ts_unix": int(now.timestamp()),
                "details": {
                    "published": 1,
                    "winner_targets": [
                        "/library/seasonal/Witch Hat Atelier/Season 01/Witch Hat Atelier - S01E01.mkv"
                    ],
                },
            },
            {
                "source": "postprocessor",
                "action": "watch-process-group",
                "message": "another event outside current week",
                "ts_unix": int((now - timedelta(days=9)).timestamp()),
                "details": {
                    "published": 1,
                    "winner_targets": [
                        "/library/seasonal/Witch Hat Atelier/Season 01/Witch Hat Atelier - S01E02.mkv"
                    ],
                },
            },
        ],
        locale="en",
    )

    today_item = payload["weekly_schedule"]["days"][now.weekday()]["items"][0]
    assert today_item["id"] == 9
    assert today_item["is_library_ready"] is True
    assert today_item["detail"]["title_raw"] == "Witch Hat Atelier"

    all_ids = {
        card["id"]
        for day in payload["weekly_schedule"]["days"]
        for card in (day["items"] + day["hidden_items"])
    }
    assert all_ids == {9}


def test_phase4_snapshot_counts_lib_from_ops_review_publish_event(tmp_path, monkeypatch):
    now = datetime(2026, 4, 8, 9, 0, tzinfo=ZoneInfo("America/Toronto"))

    class _FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def fetch_bangumi(self):
            return [
                {
                    "id": 22,
                    "official_title": "药屋少女的呢喃",
                    "air_weekday": now.weekday(),
                    "poster_link": "posters/22446688.jpg",
                    "needs_review": False,
                    "deleted": False,
                    "archived": False,
                }
            ]

    monkeypatch.setattr(service, "AutoBangumiClient", _FakeClient)

    payload = build_phase4_schedule_snapshot(
        anime_data_root=tmp_path,
        base_host="sunzhuofan.local",
        autobangumi_port=7892,
        autobangumi_base_url="http://sunzhuofan.local:7892",
        autobangumi_username="sunzhuofan",
        autobangumi_password="root1234",
        state_root=tmp_path / "ops-ui-state",
        now=now,
        events=[
            {
                "source": "ops-review",
                "action": "manual-publish",
                "message": "unrelated message text",
                "ts": now.isoformat(),
                "details": {
                    "target": "/library/seasonal/药屋少女的呢喃/Season 01/药屋少女的呢喃 - S01E01.mkv"
                },
            }
        ],
        locale="en",
    )

    today_item = payload["weekly_schedule"]["days"][now.weekday()]["items"][0]
    assert today_item["id"] == 22
    assert today_item["is_library_ready"] is True


def test_phase4_snapshot_signature_has_no_review_ids_parameter():
    params = inspect.signature(build_phase4_schedule_snapshot).parameters
    assert "review_ids" not in params


def test_phase4_snapshot_ignores_malformed_needs_review_ids(tmp_path, monkeypatch):
    now = datetime(2026, 4, 8, 9, 0, tzinfo=ZoneInfo("America/Toronto"))

    class _FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def fetch_bangumi(self):
            return [
                {
                    "id": "bad-id",
                    "official_title": "坏数据条目",
                    "air_weekday": now.weekday(),
                    "poster_link": "posters/bad.jpg",
                    "needs_review": True,
                    "deleted": False,
                    "archived": False,
                },
                {
                    "id": 101,
                    "official_title": "正常条目",
                    "air_weekday": now.weekday(),
                    "poster_link": "posters/ok.jpg",
                    "needs_review": False,
                    "deleted": False,
                    "archived": False,
                },
            ]

    monkeypatch.setattr(service, "AutoBangumiClient", _FakeClient)

    payload = build_phase4_schedule_snapshot(
        anime_data_root=tmp_path,
        base_host="sunzhuofan.local",
        autobangumi_port=7892,
        autobangumi_base_url="http://sunzhuofan.local:7892",
        autobangumi_username="sunzhuofan",
        autobangumi_password="root1234",
        state_root=tmp_path / "ops-ui-state",
        now=now,
        events=[],
        locale="en",
    )

    assert payload["weekly_schedule"]["days"][now.weekday()]["items"][0]["id"] == 101
    assert payload["weekly_schedule"]["days"][now.weekday()]["items"][0]["is_library_ready"] is False


def test_phase4_snapshot_skips_ambiguous_lib_target_matches(tmp_path, monkeypatch):
    now = datetime(2026, 4, 8, 9, 0, tzinfo=ZoneInfo("America/Toronto"))

    class _FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def fetch_bangumi(self):
            return [
                {
                    "id": 201,
                    "official_title": "同名作品",
                    "air_weekday": now.weekday(),
                    "poster_link": "posters/a.jpg",
                    "needs_review": False,
                    "deleted": False,
                    "archived": False,
                },
                {
                    "id": 202,
                    "official_title": "同名作品",
                    "air_weekday": now.weekday(),
                    "poster_link": "posters/b.jpg",
                    "needs_review": False,
                    "deleted": False,
                    "archived": False,
                },
            ]

    monkeypatch.setattr(service, "AutoBangumiClient", _FakeClient)

    payload = build_phase4_schedule_snapshot(
        anime_data_root=tmp_path,
        base_host="sunzhuofan.local",
        autobangumi_port=7892,
        autobangumi_base_url="http://sunzhuofan.local:7892",
        autobangumi_username="sunzhuofan",
        autobangumi_password="root1234",
        state_root=tmp_path / "ops-ui-state",
        now=now,
        events=[
            {
                "source": "postprocessor",
                "action": "watch-process-group",
                "ts_unix": int(now.timestamp()),
                "details": {
                    "published": 1,
                    "winner_targets": ["/library/seasonal/同名作品/Season 01/同名作品 - S01E01.mkv"],
                },
            }
        ],
        locale="en",
    )

    library_state = {
        item["id"]: item["is_library_ready"]
        for item in payload["weekly_schedule"]["days"][now.weekday()]["items"]
    }
    assert library_state[201] is False
    assert library_state[202] is False


def test_weekly_schedule_state_write_failure_is_best_effort(tmp_path, monkeypatch):
    class _FailWritePath:
        def write_text(self, *args, **kwargs):
            raise OSError("disk full")

    monkeypatch.setattr(service, "_state_path", lambda root: _FailWritePath())
    now = datetime(2026, 4, 8, 9, 0, tzinfo=ZoneInfo("America/Toronto"))

    payload = build_weekly_schedule_payload(
        bangumi_items=[
            {
                "id": 301,
                "official_title": "状态写入失败也要继续",
                "air_weekday": now.weekday(),
                "poster_link": "posters/c.jpg",
                "needs_review": False,
            }
        ],
        base_host="sunzhuofan.local",
        autobangumi_port=7892,
        library_ids=set(),
        now=now,
        state_root=tmp_path,
        locale="en",
    )

    assert payload["today_weekday"] == now.weekday()
    assert payload["days"][now.weekday()]["items"][0]["id"] == 301
