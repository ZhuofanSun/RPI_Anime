import json
import inspect
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from anime_ops_ui.services import weekly_schedule_service as service
from anime_ops_ui.services.weekly_schedule_service import (
    build_phase4_schedule_snapshot,
    build_weekly_schedule_payload,
)


def test_weekly_schedule_groups_items_today_unknown_badges_and_collapse(tmp_path):
    now = datetime(2026, 4, 8, 9, 0, tzinfo=ZoneInfo("America/Toronto"))
    payload = build_weekly_schedule_payload(
        bangumi_items=[
            {
                "id": 9,
                "official_title": "尖帽子的魔法工房",
                "air_weekday": now.weekday(),
                "poster_link": "posters/5cac94c7.jpg",
                "needs_review": False,
            },
            {
                "id": 11,
                "official_title": "相反的你和我",
                "air_weekday": now.weekday(),
                "poster_link": "posters/8d4ed23c.jpg",
                "needs_review": False,
            },
            {
                "id": 4,
                "official_title": "关于我转生变成史莱姆这档事",
                "air_weekday": None,
                "poster_link": "posters/6b0a8a03.jpg",
                "needs_review": True,
            },
        ],
        base_host="sunzhuofan.local",
        autobangumi_port=7892,
        downloaded_ids={9},
        library_ids={9},
        review_ids={9},
        now=now,
        state_root=tmp_path,
        visible_limit=1,
    )

    assert payload["today_weekday"] == now.weekday()
    assert [item["label"] for item in payload["days"]] == ["一", "二", "三", "四", "五", "六", "日"]
    assert len(payload["days"]) == 7

    today = payload["days"][now.weekday()]
    assert today["is_today"] is True
    assert today["items"][0]["poster_url"] == "http://sunzhuofan.local:7892/posters/5cac94c7.jpg"
    assert today["items"][0]["badges"] == ["DL", "LIB", "REVIEW"]
    assert today["has_hidden_items"] is True
    assert today["hidden_items"][0]["title"] == "相反的你和我"

    assert payload["unknown"]["label"] == "未知"
    assert payload["unknown"]["hint"] == "拖拽以设置放送日"
    assert payload["unknown"]["items"][0]["title"] == "关于我转生变成史莱姆这档事"
    assert payload["unknown"]["items"][0]["badges"] == ["REVIEW"]

    state = json.loads((tmp_path / "weekly_schedule_state.json").read_text(encoding="utf-8"))
    assert state["week_key"] == payload["week_key"]


def test_weekly_schedule_rewrites_state_when_iso_week_changes(tmp_path):
    first = build_weekly_schedule_payload(
        bangumi_items=[],
        base_host="sunzhuofan.local",
        autobangumi_port=7892,
        downloaded_ids=set(),
        library_ids=set(),
        review_ids=set(),
        now=datetime(2026, 4, 8, 9, 0, tzinfo=ZoneInfo("America/Toronto")),
        state_root=tmp_path,
    )
    first_state = json.loads((tmp_path / "weekly_schedule_state.json").read_text(encoding="utf-8"))

    second = build_weekly_schedule_payload(
        bangumi_items=[],
        base_host="sunzhuofan.local",
        autobangumi_port=7892,
        downloaded_ids=set(),
        library_ids=set(),
        review_ids=set(),
        now=datetime(2026, 4, 13, 9, 0, tzinfo=ZoneInfo("America/Toronto")),
        state_root=tmp_path,
    )
    second_state = json.loads((tmp_path / "weekly_schedule_state.json").read_text(encoding="utf-8"))

    assert first["week_key"] != second["week_key"]
    assert first_state["week_key"] == first["week_key"]
    assert second_state["week_key"] == second["week_key"]


def test_phase4_snapshot_derives_dl_and_lib_from_sqlite_and_events(tmp_path, monkeypatch):
    db_root = tmp_path / "appdata" / "autobangumi" / "data"
    db_root.mkdir(parents=True)
    db_path = db_root / "data.db"
    con = sqlite3.connect(db_path)
    con.execute(
        "create table torrent (id integer primary key, bangumi_id integer, downloaded boolean not null, qb_hash varchar)"
    )
    con.execute("insert into torrent (bangumi_id, downloaded, qb_hash) values (9, 1, 'hash-9')")
    con.execute("insert into torrent (bangumi_id, downloaded, qb_hash) values (11, 0, 'hash-11')")
    con.commit()
    con.close()

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
    )

    today_item = payload["today_focus"]["items"][0]
    assert today_item["id"] == 9
    assert today_item["badges"] == ["DL", "LIB"]

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
    )

    today_item = payload["today_focus"]["items"][0]
    assert today_item["id"] == 22
    assert today_item["badges"] == ["LIB"]


def test_phase4_snapshot_signature_has_no_review_ids_parameter():
    params = inspect.signature(build_phase4_schedule_snapshot).parameters
    assert "review_ids" not in params
