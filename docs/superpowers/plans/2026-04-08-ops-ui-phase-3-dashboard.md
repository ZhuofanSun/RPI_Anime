# Ops UI Phase 3 Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the `ops-ui` homepage into a control-first dashboard with a shared left navigation rail, compact service controls, and denser summary modules while preserving every current workflow from Phase 2.

**Architecture:** Keep the current FastAPI + Jinja + vanilla JS MPA structure. Add a lightweight shared navigation payload and shell hydrator for the left rail, reshape `/api/overview` into dashboard-specific sections using only existing Phase 2 data sources, and rebuild the dashboard template and CSS around the new section contract. Do not pull in new AutoBangumi/Jellyfin schedule integrations here; that remains Phase 4.

**Tech Stack:** FastAPI, Jinja2 templates, vanilla JS modules, layered CSS, pytest, requests, requests-unixsocket

---

## Scope Check

The redesign spec spans multiple phases. This implementation plan covers **only Phase 3**:

- left-side fixed navigation that keeps internal and external destinations reachable
- right-side dashboard workspace with a denser information hierarchy
- compact dashboard service controls instead of the current large service-card grid
- payload and shell changes required to support the redesign safely

This plan intentionally defers all new Phase 4 data integrations:

- no AutoBangumi weekly schedule API work
- no new “today highlights” feed sourced from subscription data
- no Jellyfin-backed “updated / downloaded / in library” rollup beyond what current Phase 2 signals already provide
- no bilingual implementation beyond continuing the copy-boundary cleanup already started in Phase 2

---

## File Structure

### Create

- `services/ops_ui/src/anime_ops_ui/services/navigation_state_service.py`
  - Shared left-rail payload builder for internal badges, external links, and tone metadata.
- `services/ops_ui/src/anime_ops_ui/services/dashboard_sections.py`
  - Small, focused helpers that translate existing overview snapshots into Phase 3 dashboard sections.
- `services/ops_ui/src/anime_ops_ui/static/shell.js`
  - Shared shell hydrator for the fixed navigation rail and compact external-service links.
- `services/ops_ui/tests/test_dashboard_contract.py`
  - Route-level and payload-level regression tests specific to the Phase 3 dashboard contract.

### Modify

- `services/ops_ui/src/anime_ops_ui/navigation.py`
  - Expand page/service metadata so the shell can render icons, labels, and stable ids without hardcoding them in templates.
- `services/ops_ui/src/anime_ops_ui/page_context.py`
  - Include shell bootstrap metadata such as the navigation API path and current page key.
- `services/ops_ui/src/anime_ops_ui/main.py`
  - Register the new `/api/navigation` route and keep `/api/overview` wired to the refactored dashboard payload.
- `services/ops_ui/src/anime_ops_ui/services/overview_service.py`
  - Replace the current “service grid + metric buckets” homepage contract with Phase 3 dashboard sections.
- `services/ops_ui/src/anime_ops_ui/templates/base.html`
  - Upgrade the shared shell so the left rail can render fixed nav items, live badges, and responsive collapse controls.
- `services/ops_ui/src/anime_ops_ui/templates/dashboard.html`
  - Replace the large service-entry layout with Phase 3 dashboard roots and skeletons.
- `services/ops_ui/src/anime_ops_ui/static/app.js`
  - Render the new dashboard hero, summary strip, pipeline cards, compact service rows, trend section, and diagnostics.
- `services/ops_ui/src/anime_ops_ui/static/styles/tokens.css`
  - Tighten the dashboard token scale for the Phase 3 information-dense layout.
- `services/ops_ui/src/anime_ops_ui/static/styles/base.css`
  - Adjust the global background, type rhythm, and reduced-motion-safe defaults where the new shell depends on them.
- `services/ops_ui/src/anime_ops_ui/static/styles/layout.css`
  - Rework the shell grid, fixed left rail, dashboard workspace columns, and responsive collapse behavior.
- `services/ops_ui/src/anime_ops_ui/static/styles/components.css`
  - Add compact nav badges, status dots, summary strips, service rows, and denser dashboard card variants.
- `services/ops_ui/src/anime_ops_ui/static/styles/pages.css`
  - Add page-specific dashboard selectors for Phase 3 without disturbing existing internal workspaces.
- `services/ops_ui/tests/test_navigation.py`
  - Cover the new navigation-state API and shell metadata.
- `services/ops_ui/tests/test_services.py`
  - Cover the new dashboard section builders and overview payload structure.
- `services/ops_ui/tests/test_contracts.py`
  - Lock the `shell.js` and rewritten `app.js` payload contracts.
- `services/ops_ui/tests/test_shell_routes.py`
  - Assert the new shell assets and dashboard roots are present and the old service-grid homepage is gone.
- `README.md`
  - Update the “前端结构” and homepage description so Phase 3 architecture is documented where the project already points contributors.

---

### Task 1: Add A Shared Navigation-State API

**Files:**
- Create: `services/ops_ui/src/anime_ops_ui/services/navigation_state_service.py`
- Create: `services/ops_ui/tests/test_dashboard_contract.py`
- Modify: `services/ops_ui/src/anime_ops_ui/main.py`
- Modify: `services/ops_ui/tests/test_navigation.py`
- Modify: `services/ops_ui/tests/test_services.py`
- Test: `services/ops_ui/tests/test_dashboard_contract.py`
- Test: `services/ops_ui/tests/test_navigation.py`

- [ ] **Step 1: Write the failing route test for the shared navigation payload**

```python
# services/ops_ui/tests/test_dashboard_contract.py
from anime_ops_ui import main as main_module


def test_navigation_state_route_returns_live_links_and_badges(client, monkeypatch):
    monkeypatch.setattr(
        main_module,
        "_env",
        lambda name, default: {
            "HOMEPAGE_BASE_HOST": "sunzhuofan.local",
            "JELLYFIN_PORT": "8096",
            "QBITTORRENT_WEBUI_PORT": "8080",
            "AUTOBANGUMI_PORT": "7892",
            "GLANCES_PORT": "61208",
            "TAILSCALE_SOCKET": "/var/run/tailscale/tailscaled.sock",
        }.get(name, default),
    )
    monkeypatch.setattr(main_module, "_count_media_files", lambda root: 4)
    monkeypatch.setattr(main_module, "read_events", lambda limit=300: [{"level": "error"}, {"level": "warning"}])
    monkeypatch.setattr(main_module, "_qb_snapshot", lambda: ({"active_downloads": 2}, None))
    monkeypatch.setattr(
        main_module,
        "_tailscale_status",
        lambda socket_path: ({"BackendState": "Running", "Self": {"Online": True}}, None),
    )

    response = client.get("/api/navigation")
    payload = response.json()

    assert response.status_code == 200
    assert payload["internal"][1]["id"] == "ops-review"
    assert payload["internal"][1]["badge"] == "4"
    assert payload["internal"][2]["tone"] == "rose"
    assert payload["external"][0]["href"] == "http://sunzhuofan.local:8096"
```

- [ ] **Step 2: Add the failing service-level test for badge rollups**

```python
# services/ops_ui/tests/test_navigation.py
from anime_ops_ui.services.navigation_state_service import build_navigation_state


def test_build_navigation_state_rolls_up_existing_counts(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "_env",
        lambda name, default: {
            "HOMEPAGE_BASE_HOST": "sunzhuofan.local",
            "JELLYFIN_PORT": "8096",
            "QBITTORRENT_WEBUI_PORT": "8080",
            "AUTOBANGUMI_PORT": "7892",
            "GLANCES_PORT": "61208",
            "TAILSCALE_SOCKET": "/var/run/tailscale/tailscaled.sock",
        }.get(name, default),
    )
    monkeypatch.setattr(main_module, "_count_media_files", lambda root: 3)
    monkeypatch.setattr(main_module, "read_events", lambda limit=300: [{"level": "error"}])
    monkeypatch.setattr(main_module, "_qb_snapshot", lambda: ({"active_downloads": 2}, None))
    monkeypatch.setattr(
        main_module,
        "_tailscale_status",
        lambda socket_path: ({"BackendState": "Running", "Self": {"Online": True}}, None),
    )

    payload = build_navigation_state()

    assert payload["internal"][1]["badge"] == "3"
    assert payload["internal"][2]["badge"] == "1"
    assert payload["external"][2]["href"] == "http://sunzhuofan.local:7892"
```

- [ ] **Step 3: Run the two new tests and verify they fail for the right reason**

Run:

```bash
./.venv/bin/python -m pytest \
  services/ops_ui/tests/test_dashboard_contract.py::test_navigation_state_route_returns_live_links_and_badges \
  services/ops_ui/tests/test_navigation.py::test_build_navigation_state_rolls_up_existing_counts \
  -q
```

Expected:

```text
E   ModuleNotFoundError: No module named 'anime_ops_ui.services.navigation_state_service'
```

- [ ] **Step 4: Implement the shared navigation-state builder and expose `/api/navigation`**

```python
# services/ops_ui/src/anime_ops_ui/services/navigation_state_service.py
from __future__ import annotations

from typing import Any

from anime_ops_ui.navigation import EXTERNAL_SERVICES, INTERNAL_PAGES


def build_navigation_state() -> dict[str, list[dict[str, Any]]]:
    from anime_ops_ui import main as main_module

    base_host = main_module._env("HOMEPAGE_BASE_HOST", main_module.socket.gethostname())
    review_count = main_module._count_media_files(main_module._manual_review_root())
    error_count = sum(1 for item in main_module.read_events(limit=300) if item.get("level") == "error")
    qb, _qb_error = main_module._qb_snapshot()
    tailscale, tailscale_error = main_module._tailscale_status(
        main_module._env("TAILSCALE_SOCKET", "/var/run/tailscale/tailscaled.sock")
    )
    tailscale_online = bool(isinstance(tailscale, dict) and (tailscale.get("Self") or {}).get("Online") and not tailscale_error)
    downloads_badge = str((qb or {}).get("active_downloads", 0) or "")

    internal = [
        {
            "id": "dashboard",
            "label": INTERNAL_PAGES["dashboard"]["label"],
            "icon": INTERNAL_PAGES["dashboard"]["icon"],
            "href": "/",
            "tone": "teal",
            "badge": None,
        },
        {
            "id": "ops-review",
            "label": INTERNAL_PAGES["ops-review"]["label"],
            "icon": INTERNAL_PAGES["ops-review"]["icon"],
            "href": "/ops-review",
            "tone": "rose" if review_count else "muted",
            "badge": str(review_count) if review_count else None,
        },
        {
            "id": "logs",
            "label": INTERNAL_PAGES["logs"]["label"],
            "icon": INTERNAL_PAGES["logs"]["icon"],
            "href": "/logs",
            "tone": "rose" if error_count else "muted",
            "badge": str(error_count) if error_count else None,
        },
        {
            "id": "postprocessor",
            "label": INTERNAL_PAGES["postprocessor"]["label"],
            "icon": INTERNAL_PAGES["postprocessor"]["icon"],
            "href": "/postprocessor",
            "tone": "amber" if downloads_badge else "muted",
            "badge": downloads_badge or None,
        },
        {
            "id": "tailscale",
            "label": INTERNAL_PAGES["tailscale"]["label"],
            "icon": INTERNAL_PAGES["tailscale"]["icon"],
            "href": "/tailscale",
            "tone": "teal" if tailscale_online else "rose",
            "badge": None,
        },
    ]

    external = [
        {
            "id": key,
            "label": item["label"],
            "icon": item["icon"],
            "href": f"http://{base_host}:{main_module._env(item['port_env'], '')}",
            "tone": "muted",
            "badge": None,
        }
        for key, item in EXTERNAL_SERVICES.items()
    ]

    return {"internal": internal, "external": external}
```

```python
# services/ops_ui/src/anime_ops_ui/main.py
from anime_ops_ui.services.navigation_state_service import build_navigation_state


@router.get("/api/navigation")
def navigation_state_api() -> JSONResponse:
    return JSONResponse(build_navigation_state())
```

- [ ] **Step 5: Re-run the new navigation tests**

Run:

```bash
./.venv/bin/python -m pytest \
  services/ops_ui/tests/test_dashboard_contract.py::test_navigation_state_route_returns_live_links_and_badges \
  services/ops_ui/tests/test_navigation.py::test_build_navigation_state_rolls_up_existing_counts \
  -q
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Commit the navigation-state foundation**

```bash
git add \
  services/ops_ui/src/anime_ops_ui/services/navigation_state_service.py \
  services/ops_ui/src/anime_ops_ui/main.py \
  services/ops_ui/tests/test_dashboard_contract.py \
  services/ops_ui/tests/test_navigation.py \
  services/ops_ui/tests/test_services.py
git commit -m "feat: add ops-ui phase3 navigation state API"
```

---

### Task 2: Hydrate The Shared Left-Rail Shell

**Files:**
- Create: `services/ops_ui/src/anime_ops_ui/static/shell.js`
- Modify: `services/ops_ui/src/anime_ops_ui/navigation.py`
- Modify: `services/ops_ui/src/anime_ops_ui/page_context.py`
- Modify: `services/ops_ui/src/anime_ops_ui/templates/base.html`
- Modify: `services/ops_ui/tests/test_contracts.py`
- Modify: `services/ops_ui/tests/test_shell_routes.py`
- Modify: `services/ops_ui/tests/test_dashboard_contract.py`
- Test: `services/ops_ui/tests/test_contracts.py`
- Test: `services/ops_ui/tests/test_shell_routes.py`

- [ ] **Step 1: Add a failing shell-markup regression test**

```python
# services/ops_ui/tests/test_shell_routes.py
def test_shared_shell_loads_phase3_nav_hydrator(client):
    response = client.get("/")
    body = response.text

    assert '/static/shell.js?v=phase3' in body
    assert 'data-shell-nav="internal"' in body
    assert 'data-nav-item="ops-review"' in body
    assert 'data-nav-badge' in body
    assert 'data-nav-toggle' in body
```

- [ ] **Step 2: Add the failing JS contract test for the shell payload**

```python
# services/ops_ui/tests/test_contracts.py
from anime_ops_ui.services.navigation_state_service import build_navigation_state


def test_navigation_payload_matches_shell_contract(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "_env",
        lambda name, default: {
            "HOMEPAGE_BASE_HOST": "sunzhuofan.local",
            "JELLYFIN_PORT": "8096",
            "QBITTORRENT_WEBUI_PORT": "8080",
            "AUTOBANGUMI_PORT": "7892",
            "GLANCES_PORT": "61208",
            "TAILSCALE_SOCKET": "/var/run/tailscale/tailscaled.sock",
        }.get(name, default),
    )
    monkeypatch.setattr(main_module, "_count_media_files", lambda root: 2)
    monkeypatch.setattr(main_module, "read_events", lambda limit=300: [])
    monkeypatch.setattr(main_module, "_qb_snapshot", lambda: ({"active_downloads": 1}, None))
    monkeypatch.setattr(main_module, "_tailscale_status", lambda socket_path: ({"Self": {"Online": True}}, None))

    payload = build_navigation_state()

    _assert_payload_matches_page_contract(payload=payload, script_name="shell.js")
```

- [ ] **Step 3: Run the shell tests and verify they fail because the shared shell is not wired yet**

Run:

```bash
./.venv/bin/python -m pytest \
  services/ops_ui/tests/test_shell_routes.py::test_shared_shell_loads_phase3_nav_hydrator \
  services/ops_ui/tests/test_contracts.py::test_navigation_payload_matches_shell_contract \
  -q
```

Expected:

```text
E   AssertionError: assert '/static/shell.js?v=phase3' in body
```

- [ ] **Step 4: Implement the shell hydrator and left-rail placeholders**

```javascript
// services/ops_ui/src/anime_ops_ui/static/shell.js
const shellApiPath = document.body.dataset.navigationApiPath || "/api/navigation";
const navToggle = document.querySelector("[data-nav-toggle]");

async function loadShellNavigation() {
  const response = await fetch(shellApiPath, { cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function applyNavItems(groupName, items) {
  const root = document.querySelector(`[data-shell-nav="${groupName}"]`);
  if (!root) return;
  items.forEach((item) => {
    const row = root.querySelector(`[data-nav-item="${item.id}"]`);
    if (!row) return;
    row.href = item.href;
    row.dataset.tone = item.tone || "muted";
    const badge = row.querySelector("[data-nav-badge]");
    if (badge) {
      badge.textContent = item.badge || "";
      badge.hidden = !item.badge;
    }
  });
}

loadShellNavigation()
  .then((payload) => {
    applyNavItems("internal", payload.internal || []);
    applyNavItems("external", payload.external || []);
  })
  .catch(() => {});

navToggle?.addEventListener("click", () => {
  document.body.classList.toggle("shell-nav-open");
});
```

```html
<!-- services/ops_ui/src/anime_ops_ui/templates/base.html -->
<body data-page="{{ page_key }}" data-navigation-api-path="{{ navigation_api_path }}">
  <button class="app-nav-toggle" type="button" data-nav-toggle aria-label="切换导航">Menu</button>
  <div class="app-shell">
    <aside class="app-nav">
      <section class="nav-group" data-shell-nav="internal">
        <h2>工作页</h2>
        {% for _key, item in internal_pages.items() %}
        <a class="nav-link{% if _key == page_key or item.path == request.url.path %} is-active{% endif %}" data-nav-item="{{ _key }}" href="{{ item.path }}">
          <span class="nav-link-icon">{{ item.icon }}</span>
          <span class="nav-link-copy">{{ item.label }}</span>
          <span class="nav-link-badge" data-nav-badge hidden></span>
        </a>
        {% endfor %}
      </section>
      <section class="nav-group" data-shell-nav="external">
        <h2>外部服务</h2>
        {% for _key, item in external_services.items() %}
        <a class="nav-link is-external" data-nav-item="{{ _key }}" href="#" target="_blank" rel="noopener noreferrer">
          <span class="nav-link-icon">{{ item.icon }}</span>
          <span class="nav-link-copy">{{ item.label }}</span>
          <span class="nav-link-badge" data-nav-badge hidden></span>
        </a>
        {% endfor %}
      </section>
    </aside>
    <main class="app-main">{% block content %}{% endblock %}</main>
  </div>
</body>
```

```python
# services/ops_ui/src/anime_ops_ui/page_context.py
def build_page_context(page_key: str, title: str) -> dict:
    return {
        "page_key": page_key,
        "page_title": title,
        "site_title": text("site.title"),
        "site_subtitle": text("site.subtitle"),
        "internal_pages": INTERNAL_PAGES,
        "external_services": EXTERNAL_SERVICES,
        "navigation_api_path": "/api/navigation",
    }
```

- [ ] **Step 5: Re-run the shell markup and contract tests**

Run:

```bash
./.venv/bin/python -m pytest \
  services/ops_ui/tests/test_shell_routes.py::test_shared_shell_loads_phase3_nav_hydrator \
  services/ops_ui/tests/test_contracts.py::test_navigation_payload_matches_shell_contract \
  -q
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Commit the shared shell work**

```bash
git add \
  services/ops_ui/src/anime_ops_ui/navigation.py \
  services/ops_ui/src/anime_ops_ui/page_context.py \
  services/ops_ui/src/anime_ops_ui/templates/base.html \
  services/ops_ui/src/anime_ops_ui/static/shell.js \
  services/ops_ui/tests/test_contracts.py \
  services/ops_ui/tests/test_shell_routes.py \
  services/ops_ui/tests/test_dashboard_contract.py
git commit -m "feat: hydrate ops-ui shared nav shell"
```

---

### Task 3: Refactor `/api/overview` Into Phase 3 Dashboard Sections

**Files:**
- Create: `services/ops_ui/src/anime_ops_ui/services/dashboard_sections.py`
- Modify: `services/ops_ui/src/anime_ops_ui/services/overview_service.py`
- Modify: `services/ops_ui/tests/test_services.py`
- Modify: `services/ops_ui/tests/test_dashboard_contract.py`
- Modify: `services/ops_ui/tests/test_contracts.py`
- Test: `services/ops_ui/tests/test_services.py`
- Test: `services/ops_ui/tests/test_dashboard_contract.py`

- [ ] **Step 1: Write the failing overview payload test for the new Phase 3 section contract**

```python
# services/ops_ui/tests/test_services.py
def test_build_overview_payload_groups_phase3_dashboard_sections(monkeypatch, tmp_path):
    data_root = tmp_path / "anime-data"
    collection_root = tmp_path / "anime-collection"
    data_root.mkdir()
    collection_root.mkdir()
    (data_root / "library" / "seasonal").mkdir(parents=True)
    (data_root / "downloads" / "Bangumi").mkdir(parents=True)
    (data_root / "processing" / "manual_review").mkdir(parents=True)

    monkeypatch.setattr(main_module, "_env", lambda name, default: {
        "ANIME_DATA_ROOT": str(data_root),
        "ANIME_COLLECTION_ROOT": str(collection_root),
        "HOMEPAGE_BASE_HOST": "sunzhuofan.local",
        "TAILSCALE_SOCKET": "/var/run/tailscale/tailscaled.sock",
    }.get(name, default))
    monkeypatch.setattr(main_module, "_sample_history_once", lambda: None)
    monkeypatch.setattr(main_module, "_safe_get_json", lambda *args, **kwargs: ({}, None))
    monkeypatch.setattr(main_module, "_qb_snapshot", lambda: ({
        "category": "Bangumi",
        "task_count": 3,
        "active_downloads": 1,
        "active_seeds": 2,
        "download_speed": 2048,
        "upload_speed": 1024,
    }, None))
    monkeypatch.setattr(main_module, "_tailscale_status", lambda socket_path: ({
        "BackendState": "Running",
        "Self": {"Online": True, "HostName": "sunzhuofan", "TailscaleIPs": ["100.123.232.73", "fd7a::1"]},
        "Peer": {},
    }, None))
    monkeypatch.setattr(main_module, "_fan_state_snapshot", lambda: ({"updated_ts": 0.0}, None))
    monkeypatch.setattr(main_module, "_series_window_hours", lambda: 24)
    monkeypatch.setattr(main_module, "_upload_window_days", lambda: 7)
    monkeypatch.setattr(main_module, "_series_values", lambda name, window_hours: ([10.0, 20.0], [10.0, 20.0]))
    monkeypatch.setattr(main_module, "_daily_volume_bars", lambda *, days, daily_key: ([{"label": "04-07", "value": 1024, "value_label": "1.0 KB"}], [1024.0]))
    monkeypatch.setattr(main_module, "_count_media_files", lambda root: 2)
    monkeypatch.setattr(main_module, "_count_series_dirs", lambda root: 1)
    monkeypatch.setattr(main_module, "read_events", lambda limit=300: [{"level": "error", "source": "postprocessor", "message": "boom"}])

    payload = build_overview_payload()

    assert payload["hero"]["title"] == "RPI Anime Ops"
    assert payload["summary_strip"][0]["question"] == "今天有什么值得看"
    assert payload["pipeline_cards"][0]["label"] == "Bangumi Tasks"
    assert payload["service_rows"][0]["id"] == "jellyfin"
```

- [ ] **Step 2: Run the new overview test and confirm the current Phase 2 payload is missing the Phase 3 keys**

Run:

```bash
./.venv/bin/python -m pytest \
  services/ops_ui/tests/test_services.py::test_build_overview_payload_groups_phase3_dashboard_sections \
  -q
```

Expected:

```text
E   KeyError: 'hero'
```

- [ ] **Step 3: Add focused section builders and reshape the overview payload**

```python
# services/ops_ui/src/anime_ops_ui/services/dashboard_sections.py
from __future__ import annotations

from typing import Any


def build_dashboard_hero(*, title: str, active_downloads: int, review_count: int, diagnostics: list[dict[str, Any]], tailnet_online: bool) -> dict[str, Any]:
    blocking_count = len([item for item in diagnostics if item.get("source") != "fan-control"])
    status_tone = "teal" if blocking_count == 0 else "rose"
    status_label = "Stable" if blocking_count == 0 else f"{blocking_count} 个风险待处理"
    return {
        "eyebrow": "Control Surface",
        "title": title,
        "summary": f"{active_downloads} 个下载中 · {review_count} 个待审核 · {'Tailnet 在线' if tailnet_online else 'Tailnet 异常'}",
        "status_tone": status_tone,
        "status_label": status_label,
    }


def build_summary_strip(*, active_downloads: int, review_count: int, diagnostics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"question": "今天有什么值得看", "answer": f"{active_downloads} 个下载中", "tone": "teal"},
        {"question": "下载和入库链路是否正常", "answer": f"{review_count} 个待审核", "tone": "amber" if review_count else "teal"},
        {"question": "设备和远程访问是否健康", "answer": "有异常" if diagnostics else "运行稳定", "tone": "rose" if diagnostics else "teal"},
    ]


def build_service_rows(services: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": item["id"],
            "name": item["name"],
            "status": item["status"],
            "meta": item["meta"],
            "uptime": item["uptime"],
            "href": item["href"],
            "internal": item.get("internal", False),
            "restart_target": item.get("restart_target"),
            "restart_label": item.get("restart_label"),
            "restart_requires_reload": item.get("restart_requires_reload", False),
            "restart_name": item.get("restart_name"),
        }
        for item in services
    ]
```

```python
# services/ops_ui/src/anime_ops_ui/services/overview_service.py
from anime_ops_ui.services.dashboard_sections import (
    build_dashboard_hero,
    build_service_rows,
    build_summary_strip,
)

# inside build_overview_payload()
hero = build_dashboard_hero(
    title=text("site.title"),
    active_downloads=int((qb or {}).get("active_downloads", 0) or 0),
    review_count=int(manual_review_count or 0),
    diagnostics=diagnostics,
    tailnet_online=bool(tailscale_self.get("Online")),
)
summary_strip = build_summary_strip(
    active_downloads=int((qb or {}).get("active_downloads", 0) or 0),
    review_count=int(manual_review_count or 0),
    diagnostics=diagnostics,
)

return {
    **page_context,
    "title": text("site.title"),
    "subtitle": text("site.subtitle"),
    "host": base_host,
    "refresh_interval_seconds": main_module._refresh_interval_seconds(),
    "hero": hero,
    "summary_strip": summary_strip,
    "pipeline_cards": queue_cards,
    "system_cards": system_cards,
    "network_cards": network_cards,
    "trend_cards": trend_cards,
    "service_rows": build_service_rows(services),
    "stack_control": {"label": "Restart Stack", "detail": "compose only · homepage last"},
    "diagnostics": diagnostics,
    "last_updated": datetime.now().isoformat(timespec="seconds"),
}
```

- [ ] **Step 4: Lock the API contract at the route level**

```python
# services/ops_ui/tests/test_dashboard_contract.py
def test_overview_route_exposes_phase3_dashboard_keys(client, monkeypatch):
    monkeypatch.setattr(main_module, "_sample_history_once", lambda: None)
    monkeypatch.setattr(main_module, "_safe_get_json", lambda *args, **kwargs: ({}, None))
    monkeypatch.setattr(main_module, "_tailscale_status", lambda *args, **kwargs: ({}, None))
    monkeypatch.setattr(main_module, "_qb_snapshot", lambda: (None, None))
    monkeypatch.setattr(main_module, "read_events", lambda limit=300: [])

    response = client.get("/api/overview")
    payload = response.json()

    assert response.status_code == 200
    assert "hero" in payload
    assert "summary_strip" in payload
    assert "service_rows" in payload
```

- [ ] **Step 5: Re-run the focused overview tests**

Run:

```bash
./.venv/bin/python -m pytest \
  services/ops_ui/tests/test_services.py::test_build_overview_payload_groups_phase3_dashboard_sections \
  services/ops_ui/tests/test_dashboard_contract.py::test_overview_route_exposes_phase3_dashboard_keys \
  -q
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Commit the Phase 3 overview payload refactor**

```bash
git add \
  services/ops_ui/src/anime_ops_ui/services/dashboard_sections.py \
  services/ops_ui/src/anime_ops_ui/services/overview_service.py \
  services/ops_ui/tests/test_services.py \
  services/ops_ui/tests/test_dashboard_contract.py \
  services/ops_ui/tests/test_contracts.py
git commit -m "feat: reshape ops-ui overview payload for phase3 dashboard"
```

---

### Task 4: Rebuild The Dashboard Template, Client Bootstrap, And Styles

**Files:**
- Modify: `services/ops_ui/src/anime_ops_ui/templates/dashboard.html`
- Modify: `services/ops_ui/src/anime_ops_ui/static/app.js`
- Modify: `services/ops_ui/src/anime_ops_ui/static/styles/tokens.css`
- Modify: `services/ops_ui/src/anime_ops_ui/static/styles/base.css`
- Modify: `services/ops_ui/src/anime_ops_ui/static/styles/layout.css`
- Modify: `services/ops_ui/src/anime_ops_ui/static/styles/components.css`
- Modify: `services/ops_ui/src/anime_ops_ui/static/styles/pages.css`
- Modify: `services/ops_ui/tests/test_shell_routes.py`
- Modify: `services/ops_ui/tests/test_contracts.py`
- Test: `services/ops_ui/tests/test_shell_routes.py`
- Test: `services/ops_ui/tests/test_contracts.py`

- [ ] **Step 1: Write the failing route test for the new dashboard roots**

```python
# services/ops_ui/tests/test_shell_routes.py
def test_dashboard_shell_contains_phase3_workspace_roots(client):
    response = client.get("/")
    body = response.text

    assert 'id="dashboard-hero"' in body
    assert 'id="dashboard-summary-strip"' in body
    assert 'id="dashboard-service-rows"' in body
    assert 'id="dashboard-pipeline-grid"' in body
    assert 'id="dashboard-status-grid"' in body
    assert 'id="services-grid"' not in body
```

- [ ] **Step 2: Rewrite the `app.js` contract test before touching the dashboard template**

```python
# services/ops_ui/tests/test_contracts.py
from anime_ops_ui.services.overview_service import build_overview_payload


def test_overview_payload_matches_phase3_dashboard_contract(monkeypatch, tmp_path):
    payload = build_overview_payload()

    _assert_payload_matches_page_contract(
        payload=payload,
        script_name="app.js",
        ignored_paths={"message"},
    )
```

- [ ] **Step 3: Run the dashboard shell and contract tests and verify they fail**

Run:

```bash
./.venv/bin/python -m pytest \
  services/ops_ui/tests/test_shell_routes.py::test_dashboard_shell_contains_phase3_workspace_roots \
  services/ops_ui/tests/test_contracts.py::test_overview_payload_matches_phase3_dashboard_contract \
  -q
```

Expected:

```text
E   AssertionError: assert 'id="dashboard-hero"' in body
```

- [ ] **Step 4: Replace the old service-grid homepage with the new Phase 3 roots and renderer**

```html
<!-- services/ops_ui/src/anime_ops_ui/templates/dashboard.html -->
<div class="page-shell dashboard-shell">
  <section id="dashboard-hero" class="dashboard-hero panel panel-wide"></section>
  <section id="dashboard-summary-strip" class="dashboard-summary-strip"></section>

  <div class="content-grid dashboard-grid">
    <section class="panel panel-wide">
      <div class="panel-head panel-head-compact">
        <div class="panel-heading">
          <h2>控制台摘要</h2>
          <p>先看结论，再看详情与动作。</p>
        </div>
        <button id="restart-stack-button" class="action-button action-button-compact action-button-secondary" type="button">
          Restart Stack
        </button>
      </div>
      <div id="service-panel-feedback" class="inline-feedback is-hidden" role="status" aria-live="polite"></div>
      <div id="dashboard-service-rows" class="dashboard-service-rows"></div>
    </section>

    <section class="panel">
      <div class="panel-head"><h2>链路状态</h2></div>
      <div id="dashboard-pipeline-grid" class="metric-grid"></div>
    </section>

    <section class="panel">
      <div class="panel-head"><h2>主机与网络</h2></div>
      <div id="dashboard-status-grid" class="metric-grid"></div>
    </section>

    <section class="panel panel-wide">
      <div class="panel-head"><h2>趋势</h2></div>
      <div id="trend-grid" class="trend-grid"></div>
    </section>

    <section class="panel panel-wide">
      <div class="panel-head"><h2>诊断</h2></div>
      <div id="diagnostics" class="diagnostics"></div>
    </section>
  </div>
</div>
```

```javascript
// services/ops_ui/src/anime_ops_ui/static/app.js
const dashboardHero = document.getElementById("dashboard-hero");
const summaryStrip = document.getElementById("dashboard-summary-strip");
const serviceRows = document.getElementById("dashboard-service-rows");
const pipelineGrid = document.getElementById("dashboard-pipeline-grid");
const statusGrid = document.getElementById("dashboard-status-grid");

function renderHero(hero) {
  dashboardHero.innerHTML = `
    <div class="dashboard-hero-copy">
      <span class="eyebrow">${hero.eyebrow}</span>
      <h1>${hero.title}</h1>
      <p>${hero.summary}</p>
    </div>
    <div class="dashboard-hero-status" data-tone="${hero.status_tone}">
      <span class="panel-badge">${hero.status_label}</span>
    </div>
  `;
}

function renderSummaryStrip(items) {
  summaryStrip.innerHTML = items
    .map(
      (item) => `
        <article class="dashboard-summary-card" data-tone="${item.tone}">
          <span class="metric-label">${item.question}</span>
          <strong class="metric-value">${item.answer}</strong>
        </article>
      `
    )
    .join("");
}

function renderServiceRows(items) {
  serviceRows.innerHTML = items.map(serviceRowTemplate).join("");
}

function renderOverview(data, { cachedAt } = {}) {
  renderHero(data.hero);
  renderSummaryStrip(data.summary_strip || []);
  renderServiceRows(data.service_rows || []);
  pipelineGrid.innerHTML = (data.pipeline_cards || []).map(metricTemplate).join("");
  statusGrid.innerHTML = [...(data.system_cards || []), ...(data.network_cards || [])].map(metricTemplate).join("");
  trendGrid.innerHTML = (data.trend_cards || []).map(trendTemplate).join("");
  diagnostics.innerHTML = diagnosticsTemplate(data.diagnostics || []);
  lastUpdated.textContent = formatUpdatedLabel(cachedAt);
}
```

```css
/* services/ops_ui/src/anime_ops_ui/static/styles/pages.css */
.dashboard-shell {
  gap: 18px;
}

.dashboard-summary-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 18px;
}

.dashboard-service-rows {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.dashboard-service-row {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: linear-gradient(180deg, var(--panel-strong), var(--panel-soft));
}
```

- [ ] **Step 5: Re-run the dashboard shell and contract tests**

Run:

```bash
./.venv/bin/python -m pytest \
  services/ops_ui/tests/test_shell_routes.py::test_dashboard_shell_contains_phase3_workspace_roots \
  services/ops_ui/tests/test_contracts.py::test_overview_payload_matches_phase3_dashboard_contract \
  -q
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Commit the dashboard UI rewrite**

```bash
git add \
  services/ops_ui/src/anime_ops_ui/templates/dashboard.html \
  services/ops_ui/src/anime_ops_ui/static/app.js \
  services/ops_ui/src/anime_ops_ui/static/styles/tokens.css \
  services/ops_ui/src/anime_ops_ui/static/styles/base.css \
  services/ops_ui/src/anime_ops_ui/static/styles/layout.css \
  services/ops_ui/src/anime_ops_ui/static/styles/components.css \
  services/ops_ui/src/anime_ops_ui/static/styles/pages.css \
  services/ops_ui/tests/test_shell_routes.py \
  services/ops_ui/tests/test_contracts.py
git commit -m "feat: rebuild ops-ui dashboard for phase3"
```

---

### Task 5: Document The New Dashboard Structure And Verify The Whole Slice

**Files:**
- Modify: `README.md`
- Test: `services/ops_ui/tests/test_navigation.py`
- Test: `services/ops_ui/tests/test_services.py`
- Test: `services/ops_ui/tests/test_contracts.py`
- Test: `services/ops_ui/tests/test_shell_routes.py`

- [ ] **Step 1: Update the README architecture section to reflect the Phase 3 shell split**

```markdown
## 前端结构

`ops-ui` 当前分成五层：

- `FastAPI` 路由与页面装配
- `services/navigation_state_service.py`
  负责共享左侧导航的 badge / tone / 外链解析
- `services/overview_service.py` + `services/dashboard_sections.py`
  负责首页控制台摘要和 Phase 3 模块化 payload
- `templates/base.html` + `static/shell.js`
  负责固定导航与共享 shell
- `templates/dashboard.html` + `static/app.js`
  负责首页具体渲染与动作绑定
```

- [ ] **Step 2: Run the full `ops_ui` test suite on the Phase 3 worktree**

Run:

```bash
./.venv/bin/python -m pytest services/ops_ui/tests -q
```

Expected:

```text
23 passed
```

- [ ] **Step 3: Run one explicit app-factory smoke check after the full suite**

Run:

```bash
./.venv/bin/python - <<'PY'
from fastapi.testclient import TestClient
from anime_ops_ui.main import create_app

with TestClient(create_app(enable_lifespan=False)) as client:
    for path in ["/", "/api/navigation", "/api/overview", "/ops-review", "/logs"]:
        response = client.get(path)
        print(path, response.status_code)
PY
```

Expected:

```text
/ 200
/api/navigation 200
/api/overview 200
/ops-review 200
/logs 200
```

- [ ] **Step 4: If desktop rendering still looks ambiguous, do a Raspberry Pi smoke check before claiming Phase 3 done**

Run:

```bash
ssh sunzhuofan@sunzhuofan.local "cd /srv/anime-data/appdata/rpi-anime && docker compose --env-file deploy/.env -f deploy/compose.yaml ps"
```

Expected:

```text
NAME                    IMAGE     COMMAND   SERVICE   CREATED   STATUS   PORTS
```

The exact container list will vary, but the command must complete successfully before using the Pi for browser-side validation.

- [ ] **Step 5: Commit the docs and verification sweep**

```bash
git add README.md
git commit -m "docs: record phase3 dashboard architecture"
```

---

## Self-Review

### Spec coverage

- Phase 3 left-nav shell: covered by Task 1 and Task 2.
- Right-side control-surface homepage: covered by Task 3 and Task 4.
- Preserve current workflows: service restart and stack restart stay in Task 3 and Task 4 through compact `service_rows`.
- Keep MPA + shared base layer: covered by Task 2 through `base.html` and `shell.js`.
- Defer Phase 4 integrations: enforced in Scope Check and in Task 3 payload rules.

### Placeholder scan

- No `TODO`, `TBD`, or “implement later” markers remain.
- Each task includes exact file paths, commands, and concrete test/code snippets.

### Type consistency

- Shared navigation payload shape is consistently `{"internal": [...], "external": [...]}` across Task 1 and Task 2.
- Dashboard payload shape is consistently `hero / summary_strip / pipeline_cards / system_cards / network_cards / trend_cards / service_rows / diagnostics` across Task 3 and Task 4.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-08-ops-ui-phase-3-dashboard.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
