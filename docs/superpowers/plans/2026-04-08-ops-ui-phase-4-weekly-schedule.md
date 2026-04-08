# Ops UI Phase 4 Weekly Schedule Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a poster-wall weekly broadcast module to the Phase 3 dashboard, using AutoBangumi as the source of truth for weekday placement and adding `DL`, `LIB`, and `REVIEW` overlays with a Monday-reset weekly window.

**Architecture:** Keep the current FastAPI + Jinja + vanilla JS MPA dashboard. Add an authenticated AutoBangumi client for the bangumi catalog, a focused weekly-schedule aggregation service that combines AutoBangumi metadata with qB/postprocessor/library overlays, and extend `/api/overview` plus the existing dashboard renderer with a new poster-wall section. Do not block Phase 4A on Jellyfin auth; use postprocessor publish events and library-path checks for `LIB`, then leave Jellyfin API integration for a later follow-up.

**Tech Stack:** FastAPI, Jinja2 templates, vanilla JS modules, layered CSS, pytest, requests, sqlite3, pathlib, zoneinfo

---

## Scope Check

This plan covers **only Phase 4A**:

- authenticated read access to AutoBangumi bangumi metadata
- dashboard `Today Focus` + weekly poster-wall schedule
- `DL`, `LIB`, and `REVIEW` overlays on posters
- a dedicated `Unknown / 未定` row for entries without `air_weekday`
- per-day vertical collapse when a column exceeds the visible threshold
- Monday-reset weekly state for overlay badges

This plan intentionally defers:

- Jellyfin username/API-key auth and direct `/Items` queries
- new standalone dashboard routes beyond the existing `/api/overview`
- editing AutoBangumi data from `ops-ui`
- Phase 5 visual polish and bilingual copy cleanup

---

## File Structure

### Create

- `services/ops_ui/src/anime_ops_ui/services/autobangumi_client.py`
  - Login-backed AutoBangumi reader for `/api/v1/auth/login` and `/api/v1/bangumi/get/all`.
- `services/ops_ui/src/anime_ops_ui/services/weekly_schedule_service.py`
  - Phase 4A aggregation layer for bangumi metadata, weekly window logic, overlay badges, and collapse metadata.
- `services/ops_ui/tests/test_autobangumi_client.py`
  - Unit tests for AutoBangumi login and bangumi fetch behavior.
- `services/ops_ui/tests/test_weekly_schedule_service.py`
  - Unit tests for weekday grouping, unknown row, Monday reset, poster URLs, and badge overlays.

### Modify

- `deploy/compose.yaml`
  - Pass `AUTOBANGUMI_USERNAME` and `AUTOBANGUMI_PASSWORD` into the `homepage` container.
- `services/ops_ui/src/anime_ops_ui/services/overview_service.py`
  - Call the new weekly schedule service and expose `today_focus` and `weekly_schedule` in the Phase 4A overview payload.
- `services/ops_ui/src/anime_ops_ui/static/app.js`
  - Render the `Today Focus` strip, seven weekday columns, unknown row, poster badges, and day-column collapse.
- `services/ops_ui/src/anime_ops_ui/templates/dashboard.html`
  - Add stable roots for the new weekly-schedule section without disturbing the existing Phase 3 shell.
- `services/ops_ui/src/anime_ops_ui/static/styles/components.css`
  - Add poster cards, weekday column chrome, badge pills, overlay rings, and collapse-toggle styling.
- `services/ops_ui/src/anime_ops_ui/static/styles/pages.css`
  - Add page-specific schedule-wall sizing and responsive stacking rules for the dashboard.
- `services/ops_ui/tests/test_dashboard_contract.py`
  - Lock the expanded `/api/overview` contract for `today_focus` and `weekly_schedule`.
- `services/ops_ui/tests/test_contracts.py`
  - Lock the `app.js` contract for the new schedule payload.
- `services/ops_ui/tests/test_shell_routes.py`
  - Assert the new dashboard roots render in server HTML.
- `README.md`
  - Document the Phase 4A dashboard module and the new AutoBangumi auth env vars.

---

### Task 1: Add The AutoBangumi Catalog Client

**Files:**
- Create: `services/ops_ui/src/anime_ops_ui/services/autobangumi_client.py`
- Create: `services/ops_ui/tests/test_autobangumi_client.py`
- Modify: `deploy/compose.yaml`
- Test: `services/ops_ui/tests/test_autobangumi_client.py`

- [ ] **Step 1: Write the failing client test for login and bangumi fetch**

```python
# services/ops_ui/tests/test_autobangumi_client.py
from anime_ops_ui.services.autobangumi_client import AutoBangumiClient


class _FakeResponse:
    def __init__(self, *, status_code=200, text="{}", json_data=None):
        self.status_code = status_code
        self.text = text
        self._json_data = {} if json_data is None else json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json_data


class _FakeSession:
    def __init__(self):
        self.posts = []
        self.gets = []

    def post(self, url, data=None, timeout=5):
        self.posts.append((url, data, timeout))
        return _FakeResponse(text='{"detail":"ok"}', json_data={"detail": "ok"})

    def get(self, url, timeout=5):
        self.gets.append((url, timeout))
        return _FakeResponse(
            json_data=[
                {
                    "id": 9,
                    "official_title": "尖帽子的魔法工房",
                    "air_weekday": 0,
                    "poster_link": "posters/5cac94c7.jpg",
                    "needs_review": False,
                    "archived": False,
                    "deleted": False,
                }
            ]
        )


def test_autobangumi_client_logs_in_and_fetches_bangumi():
    session = _FakeSession()
    client = AutoBangumiClient(
        base_url="http://ab.local:7892",
        username="sunzhuofan",
        password="root1234",
        session=session,
    )

    items = client.fetch_bangumi()

    assert session.posts == [
        (
            "http://ab.local:7892/api/v1/auth/login",
            {"username": "sunzhuofan", "password": "root1234"},
            5,
        )
    ]
    assert session.gets == [("http://ab.local:7892/api/v1/bangumi/get/all", 5)]
    assert items[0]["official_title"] == "尖帽子的魔法工房"
    assert items[0]["poster_link"] == "posters/5cac94c7.jpg"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/bin/python -m pytest services/ops_ui/tests/test_autobangumi_client.py -q`

Expected: FAIL with `ModuleNotFoundError` or `ImportError` because `autobangumi_client.py` does not exist yet.

- [ ] **Step 3: Write the minimal AutoBangumi client**

```python
# services/ops_ui/src/anime_ops_ui/services/autobangumi_client.py
from __future__ import annotations

from typing import Any

import requests


class AutoBangumiClient:
    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.session = session or requests.Session()
        self._authenticated = False

    def login(self) -> None:
        response = self.session.post(
            f"{self.base_url}/api/v1/auth/login",
            data={"username": self.username, "password": self.password},
            timeout=5,
        )
        response.raise_for_status()
        self._authenticated = True

    def fetch_bangumi(self) -> list[dict[str, Any]]:
        if not self._authenticated:
            self.login()
        response = self.session.get(f"{self.base_url}/api/v1/bangumi/get/all", timeout=5)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError("AutoBangumi bangumi payload must be a list")
        return [item for item in payload if isinstance(item, dict)]
```

- [ ] **Step 4: Pass AutoBangumi credentials through compose**

```yaml
# deploy/compose.yaml
  homepage:
    environment:
      AUTOBANGUMI_USERNAME: "${AUTOBANGUMI_USERNAME}"
      AUTOBANGUMI_PASSWORD: "${AUTOBANGUMI_PASSWORD}"
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `./.venv/bin/python -m pytest services/ops_ui/tests/test_autobangumi_client.py -q`

Expected: PASS with `1 passed`.

- [ ] **Step 6: Commit**

```bash
git add deploy/compose.yaml \
  services/ops_ui/src/anime_ops_ui/services/autobangumi_client.py \
  services/ops_ui/tests/test_autobangumi_client.py
git commit -m "feat: add autobangumi catalog client"
```

---

### Task 2: Add The Weekly Schedule Aggregation Layer

**Files:**
- Create: `services/ops_ui/src/anime_ops_ui/services/weekly_schedule_service.py`
- Create: `services/ops_ui/tests/test_weekly_schedule_service.py`
- Test: `services/ops_ui/tests/test_weekly_schedule_service.py`

- [ ] **Step 1: Write the failing service test for weekday grouping, unknown row, badges, and collapse**

```python
# services/ops_ui/tests/test_weekly_schedule_service.py
from datetime import datetime
from zoneinfo import ZoneInfo

from anime_ops_ui.services.weekly_schedule_service import build_weekly_schedule_payload


def test_weekly_schedule_groups_items_and_marks_today(tmp_path):
    payload = build_weekly_schedule_payload(
        bangumi_items=[
            {
                "id": 9,
                "official_title": "尖帽子的魔法工房",
                "air_weekday": 3,
                "poster_link": "posters/5cac94c7.jpg",
                "needs_review": False,
            },
            {
                "id": 11,
                "official_title": "相反的你和我",
                "air_weekday": 3,
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
        review_ids={4},
        now=datetime(2026, 4, 8, 9, 0, tzinfo=ZoneInfo("America/Toronto")),
        state_root=tmp_path,
        visible_limit=1,
    )

    assert payload["today_weekday"] == 3
    assert payload["days"][3]["is_today"] is True
    assert payload["days"][3]["items"][0]["poster_url"] == "http://sunzhuofan.local:7892/posters/5cac94c7.jpg"
    assert payload["days"][3]["items"][0]["badges"] == ["DL", "LIB"]
    assert payload["days"][3]["has_hidden_items"] is True
    assert payload["days"][3]["hidden_items"][0]["title"] == "相反的你和我"
    assert payload["unknown"]["items"][0]["title"] == "关于我转生变成史莱姆这档事"
    assert payload["unknown"]["items"][0]["badges"] == ["REVIEW"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/bin/python -m pytest services/ops_ui/tests/test_weekly_schedule_service.py -q`

Expected: FAIL with `ModuleNotFoundError` or missing-function errors because `weekly_schedule_service.py` does not exist yet.

- [ ] **Step 3: Write the minimal aggregation service**

```python
# services/ops_ui/src/anime_ops_ui/services/weekly_schedule_service.py
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


DAY_LABELS = ["一", "二", "三", "四", "五", "六", "日"]


def _week_key(now: datetime) -> str:
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


def _state_path(state_root: Path) -> Path:
    return state_root / "weekly_schedule_state.json"


def _poster_url(base_host: str, autobangumi_port: int, poster_link: str | None) -> str | None:
    if not poster_link:
        return None
    poster_path = str(poster_link).lstrip("/")
    return f"http://{base_host}:{autobangumi_port}/{poster_path}"


def build_weekly_schedule_payload(
    *,
    bangumi_items: list[dict[str, Any]],
    base_host: str,
    autobangumi_port: int,
    downloaded_ids: set[int],
    library_ids: set[int],
    review_ids: set[int],
    now: datetime,
    state_root: Path,
    visible_limit: int = 4,
) -> dict[str, Any]:
    state_root.mkdir(parents=True, exist_ok=True)
    week_key = _week_key(now)
    _state_path(state_root).write_text(json.dumps({"week_key": week_key}), encoding="utf-8")

    days = []
    grouped: dict[int, list[dict[str, Any]]] = {index: [] for index in range(7)}
    unknown_items: list[dict[str, Any]] = []

    for item in bangumi_items:
        badges = []
        bangumi_id = int(item.get("id"))
        if bangumi_id in downloaded_ids:
            badges.append("DL")
        if bangumi_id in library_ids:
            badges.append("LIB")
        if bangumi_id in review_ids or bool(item.get("needs_review")):
            badges.append("REVIEW")

        card = {
            "id": bangumi_id,
            "title": item.get("official_title") or item.get("title_raw") or "Unknown",
            "poster_url": _poster_url(base_host, autobangumi_port, item.get("poster_link")),
            "badges": badges,
        }
        weekday = item.get("air_weekday")
        if weekday is None:
            unknown_items.append(card)
        else:
            grouped[int(weekday)].append(card)

    for weekday in range(7):
        items = grouped[weekday]
        days.append(
            {
                "weekday": weekday,
                "label": DAY_LABELS[weekday],
                "is_today": weekday == now.weekday(),
                "items": items[:visible_limit],
                "hidden_items": items[visible_limit:],
                "has_hidden_items": len(items) > visible_limit,
            }
        )

    return {
        "week_key": week_key,
        "today_weekday": now.weekday(),
        "days": days,
        "unknown": {
            "label": "未知",
            "hint": "拖拽以设置放送日",
            "items": unknown_items,
            "hidden_items": [],
            "has_hidden_items": False,
        },
    }


def build_phase4_schedule_snapshot(
    *,
    anime_data_root: Path,
    base_host: str,
    autobangumi_port: int,
    autobangumi_base_url: str,
    autobangumi_username: str,
    autobangumi_password: str,
    state_root: Path,
    now: datetime,
    events: list[dict[str, Any]],
    visible_limit: int = 4,
) -> dict[str, Any]:
    from anime_ops_ui.services.autobangumi_client import AutoBangumiClient

    client = AutoBangumiClient(
        base_url=autobangumi_base_url,
        username=autobangumi_username,
        password=autobangumi_password,
    )
    bangumi_items = [
        item
        for item in client.fetch_bangumi()
        if not bool(item.get("deleted")) and not bool(item.get("archived"))
    ]
    review_ids = {int(item["id"]) for item in bangumi_items if bool(item.get("needs_review"))}
    schedule = build_weekly_schedule_payload(
        bangumi_items=bangumi_items,
        base_host=base_host,
        autobangumi_port=autobangumi_port,
        downloaded_ids=set(),
        library_ids=set(),
        review_ids=review_ids,
        now=now,
        state_root=state_root,
        visible_limit=visible_limit,
    )
    today_items = next(
        (day["items"] + day["hidden_items"] for day in schedule["days"] if day["is_today"]),
        [],
    )
    return {
        "today_focus": {"items": today_items[:6]},
        "weekly_schedule": schedule,
    }
```

- [ ] **Step 4: Add the failing reset and overlay-source tests before refining the implementation**

```python
def test_weekly_schedule_rewrites_state_when_iso_week_changes(tmp_path):
    from anime_ops_ui.services.weekly_schedule_service import build_weekly_schedule_payload

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

    assert first["week_key"] != second["week_key"]


def test_phase4_snapshot_derives_dl_and_lib_from_local_state(tmp_path, monkeypatch):
    import sqlite3
    from anime_ops_ui.services.weekly_schedule_service import build_phase4_schedule_snapshot

    db_root = tmp_path / "appdata" / "autobangumi" / "data"
    db_root.mkdir(parents=True)
    db_path = db_root / "data.db"
    con = sqlite3.connect(db_path)
    con.execute("create table torrent (id integer primary key, bangumi_id integer, downloaded boolean not null, qb_hash varchar)")
    con.execute("insert into torrent (bangumi_id, downloaded, qb_hash) values (9, 1, 'hash-9')")
    con.commit()
    con.close()

    monkeypatch.setattr(
        "anime_ops_ui.services.weekly_schedule_service.AutoBangumiClient.fetch_bangumi",
        lambda self: [
            {
                "id": 9,
                "official_title": "尖帽子的魔法工房",
                "air_weekday": 3,
                "poster_link": "posters/5cac94c7.jpg",
                "needs_review": False,
                "deleted": False,
                "archived": False,
            }
        ],
    )
    monkeypatch.setattr(
        "anime_ops_ui.services.weekly_schedule_service._read_postprocessor_publish_events",
        lambda events, bangumi_items, week_key: {9},
    )

    payload = build_phase4_schedule_snapshot(
        anime_data_root=tmp_path,
        base_host="sunzhuofan.local",
        autobangumi_port=7892,
        autobangumi_base_url="http://sunzhuofan.local:7892",
        autobangumi_username="sunzhuofan",
        autobangumi_password="root1234",
        state_root=tmp_path / "ops-ui-state",
        now=datetime(2026, 4, 8, 9, 0, tzinfo=ZoneInfo("America/Toronto")),
        events=[],
    )

    today_item = payload["today_focus"]["items"][0]
    assert today_item["badges"] == ["DL", "LIB"]
```

- [ ] **Step 5: Refine the snapshot builder with real overlay sources**

```python
# services/ops_ui/src/anime_ops_ui/services/weekly_schedule_service.py
import sqlite3

from anime_postprocessor.parser import normalize_title
from anime_ops_ui.services.autobangumi_client import AutoBangumiClient


def _autobangumi_db_path(anime_data_root: Path) -> Path:
    return anime_data_root / "appdata" / "autobangumi" / "data" / "data.db"


def _read_downloaded_ids_from_autobangumi_db(anime_data_root: Path) -> set[int]:
    path = _autobangumi_db_path(anime_data_root)
    if not path.exists():
        return set()
    with sqlite3.connect(path) as con:
        rows = con.execute(
            "select distinct bangumi_id from torrent where downloaded = 1 and bangumi_id is not null"
        ).fetchall()
    return {int(row[0]) for row in rows}


def _read_postprocessor_publish_events(
    events: list[dict[str, Any]],
    bangumi_items: list[dict[str, Any]],
    week_key: str,
) -> set[int]:
    import re

    title_index: dict[str, int] = {}
    published_ids: set[int] = set()
    episode_pattern = re.compile(r"^Processed (?P<title>.+?) S\d{2}E\d{2}$")

    for bangumi in bangumi_items:
        for candidate in (bangumi.get("official_title"), bangumi.get("title_raw")):
            if candidate:
                title_index[normalize_title(str(candidate))] = int(bangumi["id"])

    for item in events:
        if item.get("source") != "postprocessor" or item.get("action") != "watch-process-group":
            continue
        try:
            event_ts = datetime.fromisoformat(str(item.get("ts"))).astimezone()
        except Exception:
            continue
        if _week_key(event_ts) != week_key:
            continue
        details = item.get("details") or {}
        if not details.get("published"):
            continue
        message = str(item.get("message") or "")
        match = episode_pattern.match(message)
        if not match:
            continue
        normalized = normalize_title(match.group("title"))
        if normalized in title_index:
            published_ids.add(title_index[normalized])
    return published_ids


def build_phase4_schedule_snapshot(..., events: list[dict[str, Any]], ...) -> dict[str, Any]:
    ...
    downloaded_ids = _read_downloaded_ids_from_autobangumi_db(anime_data_root)
    library_ids = _read_postprocessor_publish_events(events, bangumi_items, _week_key(now))
    ...
    schedule = build_weekly_schedule_payload(
        bangumi_items=bangumi_items,
        base_host=base_host,
        autobangumi_port=autobangumi_port,
        downloaded_ids=downloaded_ids,
        library_ids=library_ids,
        review_ids=review_ids,
        now=now,
        state_root=state_root,
        visible_limit=visible_limit,
    )
```

- [ ] **Step 6: Run the service tests to verify they pass**

Run: `./.venv/bin/python -m pytest services/ops_ui/tests/test_weekly_schedule_service.py -q`

Expected: PASS with `3 passed`.

- [ ] **Step 7: Commit**

```bash
git add \
  services/ops_ui/src/anime_ops_ui/services/weekly_schedule_service.py \
  services/ops_ui/tests/test_weekly_schedule_service.py
git commit -m "feat: add weekly schedule aggregation service"
```

---

### Task 3: Extend The Dashboard Overview Contract

**Files:**
- Modify: `services/ops_ui/src/anime_ops_ui/services/overview_service.py`
- Modify: `services/ops_ui/tests/test_dashboard_contract.py`
- Modify: `services/ops_ui/tests/test_contracts.py`
- Test: `services/ops_ui/tests/test_dashboard_contract.py`
- Test: `services/ops_ui/tests/test_contracts.py`

- [ ] **Step 1: Write the failing overview contract test**

```python
# services/ops_ui/tests/test_dashboard_contract.py
def test_overview_api_contract_exposes_phase4_schedule_sections(client, monkeypatch):
    from anime_ops_ui import main as main_module

    monkeypatch.setattr(main_module, "_safe_get_json", lambda *args, **kwargs: ({}, None))
    monkeypatch.setattr(main_module, "_tailscale_status", lambda *args, **kwargs: ({}, None))
    monkeypatch.setattr(main_module, "_qb_snapshot", lambda: (None, None))
    monkeypatch.setattr(main_module, "_fan_state_snapshot", lambda: (None, None))
    monkeypatch.setattr(main_module, "read_events", lambda limit=300: [])
    monkeypatch.setattr(
        "anime_ops_ui.services.overview_service.build_phase4_schedule_snapshot",
        lambda **kwargs: {
            "today_focus": {"items": [{"id": 9, "title": "尖帽子的魔法工房"}]},
            "weekly_schedule": {
                "today_weekday": 3,
                "days": [{"weekday": 3, "label": "四", "is_today": True, "items": [], "hidden_items": [], "has_hidden_items": False}] * 7,
                "unknown": {"label": "未知", "items": [], "hidden_items": [], "has_hidden_items": False},
            },
        },
    )

    response = client.get("/api/overview")
    payload = response.json()

    assert response.status_code == 200
    assert "today_focus" in payload
    assert "weekly_schedule" in payload
    assert payload["weekly_schedule"]["unknown"]["label"] == "未知"
```

- [ ] **Step 2: Write the failing script contract assertion**

```python
# services/ops_ui/tests/test_contracts.py
def test_overview_payload_matches_phase4_dashboard_schedule_contract(monkeypatch, tmp_path):
    from anime_ops_ui.services.overview_service import build_overview_payload

    monkeypatch.setattr(
        "anime_ops_ui.services.overview_service.build_phase4_schedule_snapshot",
        lambda **kwargs: {
            "today_focus": {"items": [{"id": 9, "title": "尖帽子的魔法工房", "badges": ["DL"]}]},
            "weekly_schedule": {
                "today_weekday": 3,
                "days": [
                    {"weekday": index, "label": str(index), "is_today": index == 3, "items": [], "hidden_items": [], "has_hidden_items": False}
                    for index in range(7)
                ],
                "unknown": {"label": "未知", "hint": "拖拽以设置放送日", "items": [], "hidden_items": [], "has_hidden_items": False},
            },
        },
    )

    payload = build_overview_payload()
    assert payload["today_focus"]["items"][0]["badges"] == ["DL"]
    assert payload["weekly_schedule"]["days"][3]["is_today"] is True
```

- [ ] **Step 3: Run the focused tests to verify they fail**

Run: `./.venv/bin/python -m pytest services/ops_ui/tests/test_dashboard_contract.py services/ops_ui/tests/test_contracts.py -q`

Expected: FAIL because `overview_service.py` does not yet publish `today_focus` or `weekly_schedule`.

- [ ] **Step 4: Wire the Phase 4 snapshot into `build_overview_payload`**

```python
# services/ops_ui/src/anime_ops_ui/services/overview_service.py
from anime_ops_ui.services.weekly_schedule_service import build_phase4_schedule_snapshot


def build_overview_payload() -> dict[str, Any]:
    from anime_ops_ui import main as main_module
    ...
    phase4 = build_phase4_schedule_snapshot(
        anime_data_root=anime_data_root,
        base_host=base_host,
        autobangumi_port=int(main_module._env("AUTOBANGUMI_PORT", "7892")),
        autobangumi_base_url=main_module._service_link(base_host, int(main_module._env("AUTOBANGUMI_PORT", "7892"))),
        autobangumi_username=main_module._env("AUTOBANGUMI_USERNAME", ""),
        autobangumi_password=main_module._env("AUTOBANGUMI_PASSWORD", ""),
        state_root=main_module.Path(main_module._env("OPS_UI_STATE_ROOT", "/data")),
        now=datetime.now().astimezone(),
        events=main_module.read_events(limit=300),
    )
    ...
    return {
        **build_page_context(page_key="dashboard", title=text("dashboard.title")),
        "title": text("dashboard.title"),
        "subtitle": text("dashboard.subtitle"),
        "hero": build_dashboard_hero(...),
        "summary_strip": build_summary_strip(...),
        "today_focus": phase4["today_focus"],
        "weekly_schedule": phase4["weekly_schedule"],
        "pipeline_cards": queue_cards,
        "system_cards": system_cards,
        "network_cards": network_cards,
        "trend_cards": trend_cards,
        "diagnostics": diagnostics,
        "refresh_interval_seconds": 8,
        "last_updated": datetime.now().isoformat(timespec="seconds"),
    }
```

- [ ] **Step 5: Run the focused tests to verify they pass**

Run: `./.venv/bin/python -m pytest services/ops_ui/tests/test_dashboard_contract.py services/ops_ui/tests/test_contracts.py -q`

Expected: PASS with all selected tests green.

- [ ] **Step 6: Commit**

```bash
git add \
  services/ops_ui/src/anime_ops_ui/services/overview_service.py \
  services/ops_ui/tests/test_dashboard_contract.py \
  services/ops_ui/tests/test_contracts.py
git commit -m "feat: extend overview payload for phase4 schedule"
```

---

### Task 4: Render The Poster-Wall Schedule In The Dashboard

**Files:**
- Modify: `services/ops_ui/src/anime_ops_ui/templates/dashboard.html`
- Modify: `services/ops_ui/src/anime_ops_ui/static/app.js`
- Modify: `services/ops_ui/src/anime_ops_ui/static/styles/components.css`
- Modify: `services/ops_ui/src/anime_ops_ui/static/styles/pages.css`
- Modify: `services/ops_ui/tests/test_shell_routes.py`
- Modify: `services/ops_ui/tests/test_contracts.py`
- Test: `services/ops_ui/tests/test_shell_routes.py`
- Test: `services/ops_ui/tests/test_contracts.py`

- [ ] **Step 1: Write the failing route test for the new roots**

```python
# services/ops_ui/tests/test_shell_routes.py
def test_dashboard_shell_contains_phase4_schedule_roots(client):
    response = client.get("/")
    body = response.text
    assert 'id="dashboard-today-focus"' in body
    assert 'id="dashboard-weekly-schedule"' in body
    assert 'id="dashboard-unknown-schedule"' in body
    assert "broadcast-wall" in body
```

- [ ] **Step 2: Write the failing JS contract assertion**

```python
# services/ops_ui/tests/test_contracts.py
def test_app_script_reads_phase4_schedule_payload():
    required_paths = {
        "today_focus.items",
        "weekly_schedule.today_weekday",
        "weekly_schedule.days",
        "weekly_schedule.unknown",
    }
    observed = _contract_paths("app.js")
    assert required_paths.issubset(observed)
```

- [ ] **Step 3: Run the focused tests to verify they fail**

Run: `./.venv/bin/python -m pytest services/ops_ui/tests/test_shell_routes.py services/ops_ui/tests/test_contracts.py -q`

Expected: FAIL because the new roots and contract paths do not exist yet.

- [ ] **Step 4: Add the new dashboard roots**

```html
<!-- services/ops_ui/src/anime_ops_ui/templates/dashboard.html -->
<section class="panel panel-wide">
  <div class="panel-head">
    <h2>Today Focus</h2>
    <p>今天需要关注的更新、下载和入库状态。</p>
  </div>
  <div id="dashboard-today-focus" class="today-focus-grid">
    <div class="schedule-skeleton-row"></div>
  </div>
</section>

<section class="panel panel-wide">
  <div class="panel-head">
    <h2>Broadcast Wall</h2>
    <p>按 AutoBangumi 放送日分组，今天整列高亮，未知条目单独放到底部。</p>
  </div>
  <div id="dashboard-weekly-schedule" class="broadcast-wall"></div>
  <div id="dashboard-unknown-schedule" class="broadcast-wall-unknown"></div>
</section>
```

- [ ] **Step 5: Render columns, badges, and collapse in `app.js`**

```javascript
// services/ops_ui/src/anime_ops_ui/static/app.js
const todayFocus = document.getElementById("dashboard-today-focus");
const weeklySchedule = document.getElementById("dashboard-weekly-schedule");
const unknownSchedule = document.getElementById("dashboard-unknown-schedule");

function posterBadgesTemplate(item) {
  return (item.badges || [])
    .map((badge) => `<span class="schedule-badge schedule-badge-${badge.toLowerCase()}">${escapeHtml(badge)}</span>`)
    .join("");
}

function posterCardTemplate(item) {
  const image = item.poster_url
    ? `<img class="schedule-poster-image" src="${escapeHtml(item.poster_url)}" alt="${escapeHtml(item.title)}" loading="lazy">`
    : `<div class="schedule-poster-fallback">${escapeHtml((item.title || "?").slice(0, 2))}</div>`;
  return `
    <article class="schedule-poster ${item.badges?.includes("LIB") ? "is-library-ready" : ""}">
      <div class="schedule-poster-frame">
        ${image}
      </div>
      <div class="schedule-poster-overlay">
        <strong class="schedule-poster-title">${escapeHtml(item.title || "-")}</strong>
        <div class="schedule-poster-badges">${posterBadgesTemplate(item)}</div>
      </div>
    </article>
  `;
}

function dayColumnTemplate(day) {
  const visible = (day.items || []).map(posterCardTemplate).join("");
  const hidden = (day.hidden_items || []).map(posterCardTemplate).join("");
  const toggle = day.has_hidden_items
    ? `<button class="schedule-toggle" type="button" data-schedule-toggle aria-expanded="false">Show all</button>`
    : "";
  return `
    <section class="schedule-day ${day.is_today ? "is-today" : ""}">
      <header class="schedule-day-head">
        <span class="schedule-day-label">${escapeHtml(day.label || "-")}</span>
      </header>
      <div class="schedule-day-posters">${visible}</div>
      <div class="schedule-day-posters is-collapsed" data-schedule-hidden hidden>${hidden}</div>
      ${toggle}
    </section>
  `;
}

function bindScheduleToggles(root) {
  root.querySelectorAll("[data-schedule-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const container = button.parentElement?.querySelector("[data-schedule-hidden]");
      const expanded = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", expanded ? "false" : "true");
      button.textContent = expanded ? "Show all" : "Collapse";
      if (container) {
        container.hidden = expanded;
        container.classList.toggle("is-collapsed", expanded);
      }
    });
  });
}
```

- [ ] **Step 6: Add the Phase 4 render pass inside `renderOverview`**

```javascript
const focusItems = Array.isArray(data.today_focus?.items) ? data.today_focus.items : [];
todayFocus.innerHTML = focusItems.map(posterCardTemplate).join("") || '<div class="diagnostic-empty">今天没有需要特别关注的条目。</div>';

const scheduleDays = Array.isArray(data.weekly_schedule?.days) ? data.weekly_schedule.days : [];
weeklySchedule.innerHTML = scheduleDays.map(dayColumnTemplate).join("");
bindScheduleToggles(weeklySchedule);

const unknown = data.weekly_schedule?.unknown || { items: [] };
unknownSchedule.innerHTML = `
  <header class="schedule-unknown-head">
    <span>${escapeHtml(unknown.label || "未知")}</span>
    <span>${escapeHtml(unknown.hint || "")}</span>
  </header>
  <div class="schedule-unknown-posters">${(unknown.items || []).map(posterCardTemplate).join("")}</div>
`;
```

- [ ] **Step 7: Add the minimal CSS**

```css
/* services/ops_ui/src/anime_ops_ui/static/styles/components.css */
.broadcast-wall {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 1rem;
}

.schedule-day {
  padding: 0.875rem;
  border: 1px solid var(--border-subtle);
  border-radius: 1rem;
  background: var(--surface-2);
}

.schedule-day.is-today {
  border-color: color-mix(in srgb, var(--accent-teal) 55%, white 10%);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent-teal) 35%, transparent);
}

.schedule-poster.is-library-ready .schedule-poster-frame {
  outline: 2px solid color-mix(in srgb, var(--accent-teal) 65%, white 8%);
  outline-offset: 2px;
}

.schedule-badge-dl { background: rgba(245, 158, 11, 0.16); color: var(--text-strong); }
.schedule-badge-lib { background: rgba(20, 184, 166, 0.16); color: var(--text-strong); }
.schedule-badge-review { background: rgba(244, 63, 94, 0.18); color: var(--text-strong); }
```

- [ ] **Step 8: Run the focused tests and JS syntax checks**

Run:

```bash
./.venv/bin/python -m pytest services/ops_ui/tests/test_shell_routes.py services/ops_ui/tests/test_contracts.py -q
node --check services/ops_ui/src/anime_ops_ui/static/app.js
```

Expected:

- pytest PASS
- `node --check` exits `0`

- [ ] **Step 9: Commit**

```bash
git add \
  services/ops_ui/src/anime_ops_ui/templates/dashboard.html \
  services/ops_ui/src/anime_ops_ui/static/app.js \
  services/ops_ui/src/anime_ops_ui/static/styles/components.css \
  services/ops_ui/src/anime_ops_ui/static/styles/pages.css \
  services/ops_ui/tests/test_shell_routes.py \
  services/ops_ui/tests/test_contracts.py
git commit -m "feat: render phase4 weekly poster wall"
```

---

### Task 5: Document And Verify The Phase 4A Module

**Files:**
- Modify: `README.md`
- Test: `services/ops_ui/tests`

- [ ] **Step 1: Document the new env vars and dashboard module**

```markdown
<!-- README.md -->
- `AUTOBANGUMI_USERNAME`
- `AUTOBANGUMI_PASSWORD`

Phase 4A adds a weekly poster-wall schedule to the dashboard:

- AutoBangumi decides weekday placement and poster metadata
- `DL` marks items downloaded during the current ISO week
- `LIB` marks items published into the Seasonal library during the current ISO week
- `REVIEW` marks items that still need manual attention
- entries without `air_weekday` render in a dedicated `未知` row
```

- [ ] **Step 2: Run the full local verification**

Run:

```bash
./.venv/bin/python -m pytest services/ops_ui/tests -q
node --check services/ops_ui/src/anime_ops_ui/static/app.js
```

Expected:

- full test suite PASS
- `node --check` exits `0`

- [ ] **Step 3: Sync and deploy to the Raspberry Pi**

Run:

```bash
./scripts/sync_to_pi.sh
./scripts/remote_up.sh
```

Expected:

- repo sync completes successfully
- `homepage` restarts and comes back `Up`

- [ ] **Step 4: Run the real-device smoke check**

Run:

```bash
ssh sunzhuofan.local "python3 - <<'PY'
import json, urllib.request
payload = json.loads(urllib.request.urlopen('http://127.0.0.1:3000/api/overview').read().decode())
print('today_focus', bool(payload.get('today_focus')))
print('weekly_schedule', bool(payload.get('weekly_schedule')))
print('days', len(payload.get('weekly_schedule', {}).get('days', [])))
print('unknown_label', payload.get('weekly_schedule', {}).get('unknown', {}).get('label'))
PY"
```

Expected:

- `today_focus True`
- `weekly_schedule True`
- `days 7`
- `unknown_label 未知`

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: describe phase4 weekly schedule dashboard"
```

---

## Self-Review

### Spec Coverage

- `放送表`: implemented by Task 2 aggregation + Task 4 poster wall
- `今日高亮`: implemented by Task 3 overview contract + Task 4 `Today Focus`
- `本周更新状态`: implemented by Task 2 weekly window + overlay badges
- `已下载 / 已入库叠加`: implemented by Task 2 badges and Task 4 poster overlays
- `未知单独一行`: implemented by Task 2 `unknown` bucket + Task 4 bottom row
- `纵向过长可折叠`: implemented by Task 2 `has_hidden_items` + Task 4 toggle UI

No Phase 5 polish or direct Jellyfin auth work is included.

### Placeholder Scan

- No `TODO`/`TBD`
- No “similar to previous task” shortcuts
- Every task includes concrete file paths, test commands, and code snippets

### Type Consistency

- `today_focus` is always an object with `items`
- `weekly_schedule.days` is always a 7-item list of day objects
- `weekly_schedule.unknown` is always a separate object, never mixed into `days`
- poster overlay badges are always the uppercase strings `DL`, `LIB`, `REVIEW`
