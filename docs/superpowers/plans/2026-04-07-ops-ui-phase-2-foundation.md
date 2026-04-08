# Ops UI Phase 2 Foundation Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `ops-ui` into a shared-shell, service-oriented, theme-safe foundation that preserves all current behavior while preparing the codebase for the later dashboard redesign.

**Architecture:** Keep the current FastAPI + lightweight multi-page app approach, but split responsibilities into shared registries, Jinja templates, page-specific bootstraps, and backend service modules. This phase does not add the new left-nav dashboard modules yet; it builds the structure that makes that redesign safe to implement in the next phase.

**Tech Stack:** FastAPI, Jinja2 templates, vanilla JS modules, layered CSS, pytest, requests, requests-unixsocket

---

## Scope Check

The approved redesign spec includes multiple phases:

- Phase 2: code-layer decomposition and shared shell
- Phase 3: homepage layout redesign
- Phase 4: new business modules such as weekly schedule and update state
- Phase 5: full language switching and polish

This implementation plan intentionally covers **only Phase 2**. Do not mix in the new dashboard information architecture or new AutoBangumi/Jellyfin-derived modules here. The output of this plan should be a stable, testable foundation that makes Phase 3 straightforward.

---

## File Structure

### Create

- `services/ops_ui/tests/conftest.py`
  - Shared FastAPI test client and environment fixture.
- `services/ops_ui/tests/test_shell_routes.py`
  - Route-level smoke tests for internal pages and shared shell output.
- `services/ops_ui/tests/test_navigation.py`
  - Verifies navigation grouping, page metadata, and external/internal behavior.
- `services/ops_ui/tests/test_services.py`
  - Focused tests for extracted backend helpers.
- `services/ops_ui/src/anime_ops_ui/navigation.py`
  - Single source of truth for internal pages, external services, labels, and action metadata.
- `services/ops_ui/src/anime_ops_ui/copy.py`
  - Current Simplified Chinese copy map plus stable keys for later i18n.
- `services/ops_ui/src/anime_ops_ui/page_context.py`
  - Shared helpers that prepare page-level template context.
- `services/ops_ui/src/anime_ops_ui/services/__init__.py`
  - Package marker for backend service modules.
- `services/ops_ui/src/anime_ops_ui/services/overview_service.py`
  - Homepage/API aggregation and health-card composition.
- `services/ops_ui/src/anime_ops_ui/services/review_service.py`
  - `manual_review` list/detail/action data assembly.
- `services/ops_ui/src/anime_ops_ui/services/log_service.py`
  - Structured event retrieval and filtering.
- `services/ops_ui/src/anime_ops_ui/services/postprocessor_service.py`
  - Postprocessor queue and event summary shaping.
- `services/ops_ui/src/anime_ops_ui/services/tailscale_service.py`
  - Tailscale snapshot shaping and action helpers.
- `services/ops_ui/src/anime_ops_ui/templates/base.html`
  - Shared page shell with title row, theme switch, flash region, and left-nav-ready scaffold.
- `services/ops_ui/src/anime_ops_ui/templates/dashboard.html`
  - Dashboard body skeleton.
- `services/ops_ui/src/anime_ops_ui/templates/ops_review.html`
  - Review list page skeleton.
- `services/ops_ui/src/anime_ops_ui/templates/ops_review_item.html`
  - Review detail page skeleton.
- `services/ops_ui/src/anime_ops_ui/templates/logs.html`
  - Logs page skeleton.
- `services/ops_ui/src/anime_ops_ui/templates/postprocessor.html`
  - Postprocessor page skeleton.
- `services/ops_ui/src/anime_ops_ui/templates/tailscale.html`
  - Tailscale page skeleton.
- `services/ops_ui/src/anime_ops_ui/static/styles/tokens.css`
  - Shared design tokens for both light and dark themes.
- `services/ops_ui/src/anime_ops_ui/static/styles/base.css`
  - Typography, focus, reduced-motion, selection, spacing primitives.
- `services/ops_ui/src/anime_ops_ui/static/styles/layout.css`
  - Shared shell, header, page container, panel layout.
- `services/ops_ui/src/anime_ops_ui/static/styles/components.css`
  - Buttons, metric cards, status pills, nav items, flash banners.
- `services/ops_ui/src/anime_ops_ui/static/styles/pages.css`
  - Page-specific layout rules that still apply across multiple pages.
- `docs/superpowers/plans/2026-04-07-ops-ui-phase-2-foundation.md`
  - This plan.

### Modify

- `services/ops_ui/pyproject.toml`
  - Add Jinja and test dependencies.
- `services/ops_ui/src/anime_ops_ui/main.py`
  - Shrink to app wiring, route registration, static serving, and service orchestration only.
- `services/ops_ui/src/anime_ops_ui/static/core.js`
  - Shared page bootstrap helpers, query-state helpers, stale-cache handling.
- `services/ops_ui/src/anime_ops_ui/static/app.js`
  - Dashboard bootstrap rewritten against shared shell hooks.
- `services/ops_ui/src/anime_ops_ui/static/ops-review.js`
  - Review list bootstrap rewritten against shared shell hooks and URL state.
- `services/ops_ui/src/anime_ops_ui/static/ops-review-item.js`
  - Review detail bootstrap preserved but attached to new template contract.
- `services/ops_ui/src/anime_ops_ui/static/logs.js`
  - Logs bootstrap preserved but attached to new template contract.
- `services/ops_ui/src/anime_ops_ui/static/postprocessor.js`
  - Postprocessor bootstrap preserved but attached to new template contract.
- `services/ops_ui/src/anime_ops_ui/static/tailscale.js`
  - Tailscale bootstrap preserved but attached to new template contract.
- `services/ops_ui/src/anime_ops_ui/static/theme.js`
  - Theme switching must work identically with Jinja-rendered pages.
- `services/ops_ui/src/anime_ops_ui/static/styles.css`
  - Convert into import hub for layered CSS.
- `README.md`
  - Update front-end structure section after the refactor lands.

---

## Task 1: Add A Minimal Test Harness And App Factory

**Files:**
- Create: `services/ops_ui/tests/conftest.py`
- Create: `services/ops_ui/tests/test_shell_routes.py`
- Modify: `services/ops_ui/pyproject.toml`
- Modify: `services/ops_ui/src/anime_ops_ui/main.py`
- Test: `services/ops_ui/tests/test_shell_routes.py`

- [ ] **Step 1: Add test dependencies to `pyproject.toml`**

```toml
[project.optional-dependencies]
dev = [
  "httpx>=0.27.0",
  "jinja2>=3.1.4",
  "pytest>=8.3.0",
]
```

- [ ] **Step 2: Write the failing route smoke test**

```python
# services/ops_ui/tests/test_shell_routes.py
def test_internal_pages_render_successfully(client):
    for path in ["/", "/ops-review", "/logs", "/postprocessor", "/tailscale"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
```

- [ ] **Step 3: Add shared test client fixture**

```python
# services/ops_ui/tests/conftest.py
import pytest
from fastapi.testclient import TestClient

from anime_ops_ui.main import create_app


@pytest.fixture()
def client():
    with TestClient(create_app()) as test_client:
        yield test_client
```

- [ ] **Step 4: Run the test to verify it fails**

Run:

```bash
python3 -m pytest services/ops_ui/tests/test_shell_routes.py -q
```

Expected:

```text
E   ImportError: cannot import name 'create_app'
```

- [ ] **Step 5: Extract an app factory from `main.py`**

```python
def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    register_routes(app)
    return app


def main() -> None:
    import uvicorn
    uvicorn.run(create_app(), host="0.0.0.0", port=3000)
```

- [ ] **Step 6: Re-run the smoke test**

Run:

```bash
python3 -m pytest services/ops_ui/tests/test_shell_routes.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 7: Commit**

```bash
git add services/ops_ui/pyproject.toml services/ops_ui/tests/conftest.py services/ops_ui/tests/test_shell_routes.py services/ops_ui/src/anime_ops_ui/main.py
git commit -m "refactor: add ops-ui app factory and test harness"
```

---

## Task 2: Introduce Navigation, Copy, And Shared Page Context

**Files:**
- Create: `services/ops_ui/src/anime_ops_ui/navigation.py`
- Create: `services/ops_ui/src/anime_ops_ui/copy.py`
- Create: `services/ops_ui/src/anime_ops_ui/page_context.py`
- Create: `services/ops_ui/tests/test_navigation.py`
- Modify: `services/ops_ui/src/anime_ops_ui/main.py`
- Test: `services/ops_ui/tests/test_navigation.py`

- [ ] **Step 1: Write a failing test for internal/external navigation metadata**

```python
from anime_ops_ui.navigation import INTERNAL_PAGES, EXTERNAL_SERVICES


def test_navigation_registry_contains_expected_groups():
    assert "dashboard" in INTERNAL_PAGES
    assert INTERNAL_PAGES["dashboard"]["path"] == "/"
    assert EXTERNAL_SERVICES["jellyfin"]["target"] == "external"
    assert EXTERNAL_SERVICES["qbittorrent"]["port_env"] == "QBITTORRENT_WEBUI_PORT"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python3 -m pytest services/ops_ui/tests/test_navigation.py -q
```

Expected:

```text
E   ModuleNotFoundError: No module named 'anime_ops_ui.navigation'
```

- [ ] **Step 3: Add the navigation registry**

```python
# services/ops_ui/src/anime_ops_ui/navigation.py
INTERNAL_PAGES = {
    "dashboard": {"label": "Dashboard", "path": "/", "icon": "D", "target": "internal"},
    "ops_review": {"label": "Ops Review", "path": "/ops-review", "icon": "OR", "target": "internal"},
    "logs": {"label": "Logs", "path": "/logs", "icon": "L", "target": "internal"},
    "postprocessor": {"label": "Postprocessor", "path": "/postprocessor", "icon": "P", "target": "internal"},
    "tailscale": {"label": "Tailscale", "path": "/tailscale", "icon": "T", "target": "internal"},
}

EXTERNAL_SERVICES = {
    "jellyfin": {"label": "Jellyfin", "icon": "J", "target": "external", "port_env": "JELLYFIN_PORT"},
    "qbittorrent": {"label": "qBittorrent", "icon": "Q", "target": "external", "port_env": "QBITTORRENT_WEBUI_PORT"},
    "autobangumi": {"label": "AutoBangumi", "icon": "A", "target": "external", "port_env": "AUTOBANGUMI_PORT"},
    "glances": {"label": "Glances", "icon": "G", "target": "external", "port_env": "GLANCES_PORT"},
}
```

- [ ] **Step 4: Add a stable copy map and page context helper**

```python
# services/ops_ui/src/anime_ops_ui/copy.py
COPY = {
    "site.title": "RPI Anime Ops",
    "site.subtitle": "树莓派私人影音库控制台",
    "nav.external": "外部服务",
    "nav.internal": "工作页",
}


def text(key: str) -> str:
    return COPY[key]
```

```python
# services/ops_ui/src/anime_ops_ui/page_context.py
from anime_ops_ui.copy import text
from anime_ops_ui.navigation import EXTERNAL_SERVICES, INTERNAL_PAGES


def build_page_context(page_key: str, title: str) -> dict:
    return {
        "page_key": page_key,
        "page_title": title,
        "site_title": text("site.title"),
        "site_subtitle": text("site.subtitle"),
        "internal_pages": INTERNAL_PAGES,
        "external_services": EXTERNAL_SERVICES,
    }
```

- [ ] **Step 5: Re-run the navigation tests**

Run:

```bash
python3 -m pytest services/ops_ui/tests/test_navigation.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 6: Commit**

```bash
git add services/ops_ui/src/anime_ops_ui/navigation.py services/ops_ui/src/anime_ops_ui/copy.py services/ops_ui/src/anime_ops_ui/page_context.py services/ops_ui/tests/test_navigation.py services/ops_ui/src/anime_ops_ui/main.py
git commit -m "refactor: add ops-ui navigation and copy registries"
```

---

## Task 3: Introduce A Shared Jinja Shell For Internal Pages

**Files:**
- Create: `services/ops_ui/src/anime_ops_ui/templates/base.html`
- Create: `services/ops_ui/src/anime_ops_ui/templates/dashboard.html`
- Create: `services/ops_ui/src/anime_ops_ui/templates/ops_review.html`
- Create: `services/ops_ui/src/anime_ops_ui/templates/ops_review_item.html`
- Create: `services/ops_ui/src/anime_ops_ui/templates/logs.html`
- Create: `services/ops_ui/src/anime_ops_ui/templates/postprocessor.html`
- Create: `services/ops_ui/src/anime_ops_ui/templates/tailscale.html`
- Modify: `services/ops_ui/pyproject.toml`
- Modify: `services/ops_ui/src/anime_ops_ui/main.py`
- Modify: `services/ops_ui/tests/test_shell_routes.py`
- Test: `services/ops_ui/tests/test_shell_routes.py`

- [ ] **Step 1: Extend the route smoke test to assert the shared shell**

```python
def test_dashboard_uses_shared_shell(client):
    response = client.get("/")
    body = response.text
    assert "app-shell" in body
    assert "Dashboard" in body
    assert "Ops Review" in body
    assert "Jellyfin" in body
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python3 -m pytest services/ops_ui/tests/test_shell_routes.py::test_dashboard_uses_shared_shell -q
```

Expected:

```text
E   AssertionError: assert 'app-shell' in '<!doctype html>...'
```

- [ ] **Step 3: Add the base template**

```html
<!-- services/ops_ui/src/anime_ops_ui/templates/base.html -->
<!doctype html>
<html lang="zh-Hans">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{{ page_title }} · {{ site_title }}</title>
    <link rel="stylesheet" href="/static/styles.css?v=phase2" />
    <script defer src="/static/theme.js?v=phase2"></script>
    {% block head %}{% endblock %}
  </head>
  <body data-page="{{ page_key }}">
    <div class="app-shell">
      <aside class="app-nav">
        <section class="nav-group">
          <h2>工作页</h2>
          {% for _key, item in internal_pages.items() %}
          <a class="nav-link{% if item.path == request.url.path %} is-active{% endif %}" href="{{ item.path }}">{{ item.label }}</a>
          {% endfor %}
        </section>
        <section class="nav-group">
          <h2>外部服务</h2>
          {% for _key, item in external_services.items() %}
          <span class="nav-link is-external">{{ item.label }}</span>
          {% endfor %}
        </section>
      </aside>
      <main class="app-main">{% block content %}{% endblock %}</main>
    </div>
  </body>
</html>
```

- [ ] **Step 4: Promote `jinja2` to a runtime dependency**

```toml
[project]
dependencies = [
  "fastapi>=0.116.0",
  "jinja2>=3.1.4",
  "requests>=2.31.0",
  "requests-unixsocket>=0.4.1",
  "uvicorn>=0.35.0",
]

[project.optional-dependencies]
dev = [
  "httpx>=0.27.0",
  "pytest>=8.3.0",
]
```

- [ ] **Step 5: Add one page template and wire the route through Jinja**

```html
<!-- services/ops_ui/src/anime_ops_ui/templates/dashboard.html -->
{% extends "base.html" %}
{% block head %}
<script defer src="/static/core.js?v=phase2"></script>
<script defer src="/static/app.js?v=phase2"></script>
{% endblock %}
{% block content %}
<section class="page-hero">
  <h1>{{ page_title }}</h1>
  <p>{{ site_subtitle }}</p>
</section>
<section id="dashboard-root"></section>
{% endblock %}
```

```python
from fastapi.templating import Jinja2Templates

TEMPLATES = Jinja2Templates(directory=str(APP_DIR / "templates"))


def render_page(request: Request, template_name: str, page_key: str, title: str):
    context = build_page_context(page_key, title)
    return TEMPLATES.TemplateResponse(
        request,
        template_name,
        {"request": request, **context},
    )
```

- [ ] **Step 6: Convert the remaining internal pages to the same shell**

```python
PAGE_TEMPLATES = {
    "/": ("dashboard.html", "dashboard", "Dashboard"),
    "/ops-review": ("ops_review.html", "ops-review", "Ops Review"),
    "/ops-review/item": ("ops_review_item.html", "ops-review", "Review Detail"),
    "/logs": ("logs.html", "logs", "Logs"),
    "/postprocessor": ("postprocessor.html", "postprocessor", "Postprocessor"),
    "/tailscale": ("tailscale.html", "tailscale", "Tailscale"),
}
```

- [ ] **Step 7: Re-run the shell tests**

Run:

```bash
.venv/bin/python -m pytest services/ops_ui/tests/test_shell_routes.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 8: Commit**

```bash
git add services/ops_ui/pyproject.toml services/ops_ui/src/anime_ops_ui/templates services/ops_ui/src/anime_ops_ui/main.py services/ops_ui/tests/test_shell_routes.py
git commit -m "refactor: move ops-ui internal pages to shared Jinja shell"
```

---

## Task 4: Split `main.py` Into Focused Backend Service Modules

**Files:**
- Create: `services/ops_ui/src/anime_ops_ui/services/overview_service.py`
- Create: `services/ops_ui/src/anime_ops_ui/services/review_service.py`
- Create: `services/ops_ui/src/anime_ops_ui/services/log_service.py`
- Create: `services/ops_ui/src/anime_ops_ui/services/postprocessor_service.py`
- Create: `services/ops_ui/src/anime_ops_ui/services/tailscale_service.py`
- Create: `services/ops_ui/tests/test_services.py`
- Modify: `services/ops_ui/src/anime_ops_ui/main.py`
- Test: `services/ops_ui/tests/test_services.py`

- [ ] **Step 1: Write a failing unit test around one extracted service**

```python
from anime_ops_ui.services.overview_service import build_service_summary


def test_build_service_summary_counts_tailscaled():
    summary = build_service_summary(
        containers={"jellyfin": {"status": "running"}, "qbittorrent": {"status": "exited"}},
        tailscale_running=True,
    )
    assert summary["value"] == "2 online"
    assert summary["detail"] == "3 total · Docker + tailscaled"
```

- [ ] **Step 2: Run the service test to verify it fails**

Run:

```bash
python3 -m pytest services/ops_ui/tests/test_services.py -q
```

Expected:

```text
E   ModuleNotFoundError: No module named 'anime_ops_ui.services'
```

- [ ] **Step 3: Extract the service module**

```python
# services/ops_ui/src/anime_ops_ui/services/overview_service.py
def build_service_summary(*, containers: dict, tailscale_running: bool) -> dict:
    running_containers = sum(1 for item in containers.values() if str(item.get("status", "")).lower() == "running")
    total = len(containers) + 1
    online = running_containers + (1 if tailscale_running else 0)
    return {
        "label": "Services",
        "value": f"{online} online",
        "detail": f"{total} total · Docker + tailscaled",
    }
```

- [ ] **Step 4: Move remaining helper families into dedicated modules**

```python
# services/ops_ui/src/anime_ops_ui/services/log_service.py
def list_log_events(*, source: str | None = None, level: str | None = None, query: str | None = None) -> dict[str, Any]:
    return build_logs_payload(source=source, level=level, query=query)

# services/ops_ui/src/anime_ops_ui/services/review_service.py
def list_manual_review_items() -> dict[str, Any]:
    return build_manual_review_payload()


def get_manual_review_item(item_id: str) -> dict[str, Any]:
    return build_manual_review_item_payload(item_id)

# services/ops_ui/src/anime_ops_ui/services/postprocessor_service.py
def build_postprocessor_snapshot() -> dict[str, Any]:
    return build_postprocessor_payload()

# services/ops_ui/src/anime_ops_ui/services/tailscale_service.py
def build_tailscale_snapshot() -> dict[str, Any]:
    return build_tailscale_payload()
```

- [ ] **Step 5: Shrink `main.py` to route registration and orchestration**

```python
@app.get("/api/overview")
def api_overview() -> JSONResponse:
    payload = build_overview()
    return JSONResponse(payload)
```

- [ ] **Step 6: Run the tests**

Run:

```bash
python3 -m pytest services/ops_ui/tests/test_services.py services/ops_ui/tests/test_shell_routes.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 7: Commit**

```bash
git add services/ops_ui/src/anime_ops_ui/services services/ops_ui/src/anime_ops_ui/main.py services/ops_ui/tests/test_services.py
git commit -m "refactor: split ops-ui backend helpers into service modules"
```

---

## Task 5: Layer The Stylesheet And Normalize Shared Front-End Bootstraps

**Files:**
- Create: `services/ops_ui/src/anime_ops_ui/static/styles/tokens.css`
- Create: `services/ops_ui/src/anime_ops_ui/static/styles/base.css`
- Create: `services/ops_ui/src/anime_ops_ui/static/styles/layout.css`
- Create: `services/ops_ui/src/anime_ops_ui/static/styles/components.css`
- Create: `services/ops_ui/src/anime_ops_ui/static/styles/pages.css`
- Modify: `services/ops_ui/src/anime_ops_ui/static/styles.css`
- Modify: `services/ops_ui/src/anime_ops_ui/static/core.js`
- Modify: `services/ops_ui/src/anime_ops_ui/static/app.js`
- Modify: `services/ops_ui/src/anime_ops_ui/static/ops-review.js`
- Modify: `services/ops_ui/src/anime_ops_ui/static/ops-review-item.js`
- Modify: `services/ops_ui/src/anime_ops_ui/static/logs.js`
- Modify: `services/ops_ui/src/anime_ops_ui/static/postprocessor.js`
- Modify: `services/ops_ui/src/anime_ops_ui/static/tailscale.js`
- Test: `services/ops_ui/tests/test_shell_routes.py`

- [ ] **Step 1: Add a failing test that asserts the new shared shell still renders the page root hooks**

```python
def test_dashboard_shell_contains_bootstrap_roots(client):
    response = client.get("/")
    body = response.text
    assert 'data-page="dashboard"' in body
    assert 'id="dashboard-root"' in body
```

- [ ] **Step 2: Run the test to verify current shell coverage**

Run:

```bash
python3 -m pytest services/ops_ui/tests/test_shell_routes.py::test_dashboard_shell_contains_bootstrap_roots -q
```

Expected:

```text
1 passed
```

This is a guardrail step. Do not skip it.

- [ ] **Step 3: Convert `styles.css` into an import hub**

```css
@import url("/static/styles/tokens.css?v=phase2");
@import url("/static/styles/base.css?v=phase2");
@import url("/static/styles/layout.css?v=phase2");
@import url("/static/styles/components.css?v=phase2");
@import url("/static/styles/pages.css?v=phase2");
```

- [ ] **Step 4: Move the theme-critical tokens into `tokens.css`**

```css
:root {
  --bg: #f7f5ef;
  --panel: #ffffff;
  --text: #13202b;
  --muted: #6c7683;
  --accent: #4aa4a6;
  --danger: #cf4a66;
}

:root[data-theme="dark"] {
  --bg: #0c1218;
  --panel: #121a22;
  --text: #eef5f5;
  --muted: #9eabb5;
  --accent: #5ab7b6;
  --danger: #f06a82;
}
```

- [ ] **Step 5: Add a shared bootstrap helper in `core.js`**

```javascript
function createPageBootstrap({ cacheKey, fetcher, render, intervalMs, shouldPause }) {
  let isBusy = false;

  async function tick() {
    if (isBusy || (shouldPause && shouldPause())) return;
    isBusy = true;
    try {
      const payload = await fetcher();
      render(payload);
      writeSessionCache(cacheKey, payload);
    } finally {
      isBusy = false;
    }
  }

  return { tick };
}
```

- [ ] **Step 6: Update each page script to use the shared bootstrap contract**

```javascript
const page = AnimeOpsCore.createPageBootstrap({
  cacheKey: "overview-cache-v3",
  fetcher: fetchOverview,
  render: renderOverview,
  intervalMs: 8000,
});
```

- [ ] **Step 7: Run smoke tests after CSS/JS reshaping**

Run:

```bash
python3 -m pytest services/ops_ui/tests/test_shell_routes.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 8: Commit**

```bash
git add services/ops_ui/src/anime_ops_ui/static/styles.css services/ops_ui/src/anime_ops_ui/static/styles services/ops_ui/src/anime_ops_ui/static/core.js services/ops_ui/src/anime_ops_ui/static/app.js services/ops_ui/src/anime_ops_ui/static/ops-review.js services/ops_ui/src/anime_ops_ui/static/ops-review-item.js services/ops_ui/src/anime_ops_ui/static/logs.js services/ops_ui/src/anime_ops_ui/static/postprocessor.js services/ops_ui/src/anime_ops_ui/static/tailscale.js
git commit -m "refactor: layer ops-ui styles and normalize page bootstraps"
```

---

## Task 6: Finish With Documentation And End-To-End Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/frontend-refactor.md` (archive note only)
- Modify: `services/ops_ui/src/anime_ops_ui/main.py`
- Test: `services/ops_ui/tests/test_shell_routes.py`
- Test: `services/ops_ui/tests/test_navigation.py`
- Test: `services/ops_ui/tests/test_services.py`

- [ ] **Step 1: Update the README front-end structure section**

```md
## 前端结构

`ops-ui` 当前分成四层：

- FastAPI 路由与页面装配
- `services/*` 后端数据聚合
- Jinja 共享页面 shell
- `static/` 前端引导与样式层
```

- [ ] **Step 2: Keep `docs/frontend-refactor.md` as an archive note**

```md
这份文件只保留归档说明，不再作为主文档。
```

- [ ] **Step 3: Run the full ops-ui test suite**

Run:

```bash
python3 -m pytest services/ops_ui/tests -q
```

Expected:

```text
5 passed
```

- [ ] **Step 4: Run front-end syntax checks**

Run:

```bash
node --check services/ops_ui/src/anime_ops_ui/static/core.js
node --check services/ops_ui/src/anime_ops_ui/static/app.js
node --check services/ops_ui/src/anime_ops_ui/static/ops-review.js
node --check services/ops_ui/src/anime_ops_ui/static/ops-review-item.js
node --check services/ops_ui/src/anime_ops_ui/static/logs.js
node --check services/ops_ui/src/anime_ops_ui/static/postprocessor.js
node --check services/ops_ui/src/anime_ops_ui/static/tailscale.js
```

Expected:

```text
No output, exit code 0
```

- [ ] **Step 5: Run manual verification locally**

Run:

```bash
python3 -m uvicorn anime_ops_ui.main:create_app --factory --host 127.0.0.1 --port 3000
```

Verify:

- `/` renders the shared shell
- `/ops-review`, `/logs`, `/postprocessor`, `/tailscale` all use the same shell
- Theme switch still works in both light and dark
- External service links still open in a new tab
- Internal page links stay in-site
- No current feature regresses

- [ ] **Step 6: Commit**

```bash
git add README.md docs/frontend-refactor.md services/ops_ui/tests services/ops_ui/src/anime_ops_ui
git commit -m "docs: finalize ops-ui phase 2 foundation refactor"
```

---

## Spec Coverage Self-Review

### Covered From Spec

- Shared shell and reduced HTML duplication: Tasks 2 and 3
- Code-layer decomposition and clearer backend boundaries: Task 4
- Theme parity and style layering prep: Task 5
- i18n preparation via copy registry and terminology consolidation: Task 2
- Internal/external navigation split preserved: Tasks 2 and 3
- Performance-safe MPA approach preserved: Tasks 1, 3, and 5

### Explicitly Deferred To Later Phases

- New left-side fixed navigation as the dominant homepage layout
- Homepage replacement of the current 8 large service cards
- AutoBangumi/Jellyfin-derived business modules such as weekly schedule and update state
- Full language switcher UI

These deferrals are intentional and match the approved spec.

### Placeholder Scan

Plan checked for:

- `TODO`
- `TBD`
- “implement later”
- “similar to”
- vague “add tests”

None are left in the task steps.

---

Plan complete and saved to `docs/superpowers/plans/2026-04-07-ops-ui-phase-2-foundation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
