# Ops UI Dashboard Density Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compress the dashboard hero, restyle the shared theme/language controls into compact right-aligned segmented buttons on every page, align the first summary-strip answer with the count of `LIB`-outlined schedule cards, and rebalance the dashboard middle section by moving `Trends` above `Pipeline` while making `Pipeline` more visual and less text-heavy.

**Architecture:** Keep the current FastAPI + Jinja + vanilla JS MPA structure. Reuse the existing overview payload and weekly schedule snapshot, derive the library-ready summary count from the same schedule data that renders the wall, and limit changes to shared shell markup, dashboard layout/styles, and overview-section shaping. Do not add new endpoints or new backend integrations.

**Tech Stack:** FastAPI, Jinja2, vanilla JS, layered CSS, pytest

---

## File Structure

### Modify

- `services/ops_ui/src/anime_ops_ui/templates/_preferences_controls.html`
  - Remove the heavy preferences card header and switch to compact dual segmented groups.
- `services/ops_ui/src/anime_ops_ui/static/styles/components.css`
  - Restyle shared preference controls, tighten hero spacing, and add new pipeline/state visuals.
- `services/ops_ui/src/anime_ops_ui/static/styles/pages.css`
  - Rebalance dashboard section ordering and responsive layout.
- `services/ops_ui/src/anime_ops_ui/templates/dashboard.html`
  - Reorder `Trends / Host + Network / Pipeline` roots and slim the hero structure.
- `services/ops_ui/src/anime_ops_ui/services/dashboard_sections.py`
  - Update summary-strip construction to accept a library-ready count.
- `services/ops_ui/src/anime_ops_ui/services/overview_service.py`
  - Derive the first summary answer from the rendered weekly schedule snapshot and keep section payloads stable.
- `services/ops_ui/src/anime_ops_ui/static/app.js`
  - Render the new pipeline visual treatment without changing the weekly wall contract.
- `services/ops_ui/tests/test_services.py`
  - Lock the summary-strip count derivation.
- `services/ops_ui/tests/test_dashboard_contract.py`
  - Lock the overview payload behavior and dashboard section ordering assumptions.
- `services/ops_ui/tests/test_shell_routes.py`
  - Lock the compact shared preference controls and dashboard root order in SSR HTML.
- `services/ops_ui/tests/test_contracts.py`
  - Lock the CSS/JS contract for compact preferences and the updated pipeline renderer.

---

### Task 1: Compact The Shared Preference Controls

**Files:**
- Modify: `services/ops_ui/src/anime_ops_ui/templates/_preferences_controls.html`
- Modify: `services/ops_ui/src/anime_ops_ui/static/styles/components.css`
- Modify: `services/ops_ui/tests/test_shell_routes.py`
- Modify: `services/ops_ui/tests/test_contracts.py`

- [ ] **Step 1: Write failing shell-route assertions for the compact control shape**

Add assertions to `services/ops_ui/tests/test_shell_routes.py` that server-rendered pages:
- still contain exactly one `data-preferences-controls`
- no longer render `.preferences-header`
- render exactly two `.segmented-control` groups

- [ ] **Step 2: Run the focused shell test and verify it fails**

Run:

```bash
/Users/sunzhuofan/RPI_Anime/.venv/bin/python -m pytest services/ops_ui/tests/test_shell_routes.py::test_all_shell_pages_render_shared_preferences_once -q
```

Expected: FAIL because the old shared preferences markup still includes the header and row layout.

- [ ] **Step 3: Replace the shared preferences markup with compact dual segments**

Implement in `services/ops_ui/src/anime_ops_ui/templates/_preferences_controls.html`:

```jinja
<section class="preferences-controls" data-preferences-controls aria-label="{{ shell_copy.preferences.title }}">
  <div class="preferences-segment">
    <div class="segmented-control" role="group" aria-label="{{ shell_copy.preferences.theme }}">
      ...
    </div>
  </div>
  <div class="preferences-segment">
    <div class="segmented-control" role="group" aria-label="{{ shell_copy.preferences.language }}">
      ...
    </div>
  </div>
</section>
```

- [ ] **Step 4: Tighten the shared-control CSS**

Update `services/ops_ui/src/anime_ops_ui/static/styles/components.css` so:
- `.preferences-controls` becomes an inline flex row instead of a boxed mini-card
- the groups stay right-aligned in hero meta regions
- active/focus states remain clear
- mobile wrapping still works

- [ ] **Step 5: Run focused shell/CSS contract tests**

Run:

```bash
/Users/sunzhuofan/RPI_Anime/.venv/bin/python -m pytest \
  services/ops_ui/tests/test_shell_routes.py \
  services/ops_ui/tests/test_contracts.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/ops_ui/src/anime_ops_ui/templates/_preferences_controls.html \
  services/ops_ui/src/anime_ops_ui/static/styles/components.css \
  services/ops_ui/tests/test_shell_routes.py \
  services/ops_ui/tests/test_contracts.py
git commit -m "refactor: compact shared preference controls"
```

---

### Task 2: Align The First Summary Answer With Library-Ready Posters

**Files:**
- Modify: `services/ops_ui/src/anime_ops_ui/services/dashboard_sections.py`
- Modify: `services/ops_ui/src/anime_ops_ui/services/overview_service.py`
- Modify: `services/ops_ui/tests/test_services.py`
- Modify: `services/ops_ui/tests/test_dashboard_contract.py`

- [ ] **Step 1: Write the failing service test for the library-ready summary count**

Extend `services/ops_ui/tests/test_services.py` so the first summary answer expects the count of `is_library_ready=True` items across:
- visible weekday items
- hidden weekday items
- visible unknown items
- hidden unknown items

- [ ] **Step 2: Run the focused overview/service test and verify it fails**

Run:

```bash
/Users/sunzhuofan/RPI_Anime/.venv/bin/python -m pytest \
  services/ops_ui/tests/test_services.py::test_build_overview_payload_matches_phase3_contract \
  services/ops_ui/tests/test_dashboard_contract.py::test_overview_api_contract_exposes_phase3_sections -q
```

Expected: FAIL because the first summary answer still uses active download count.

- [ ] **Step 3: Add a schedule-derived library-ready counter**

Implement a helper in `services/ops_ui/src/anime_ops_ui/services/overview_service.py`:

```python
def _count_library_ready_schedule_items(schedule: dict[str, Any]) -> int:
    ...
```

It must count `is_library_ready` across all visible and hidden schedule collections.

- [ ] **Step 4: Thread the new count into the summary-strip builder**

Change `build_summary_strip()` in `services/ops_ui/src/anime_ops_ui/services/dashboard_sections.py` to accept `library_ready_count` and use it for the first answer.

- [ ] **Step 5: Run the focused tests again**

Run:

```bash
/Users/sunzhuofan/RPI_Anime/.venv/bin/python -m pytest \
  services/ops_ui/tests/test_services.py \
  services/ops_ui/tests/test_dashboard_contract.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/ops_ui/src/anime_ops_ui/services/dashboard_sections.py \
  services/ops_ui/src/anime_ops_ui/services/overview_service.py \
  services/ops_ui/tests/test_services.py \
  services/ops_ui/tests/test_dashboard_contract.py
git commit -m "feat: align summary strip with library-ready posters"
```

---

### Task 3: Reorder The Dashboard And Make Pipeline More Visual

**Files:**
- Modify: `services/ops_ui/src/anime_ops_ui/templates/dashboard.html`
- Modify: `services/ops_ui/src/anime_ops_ui/static/app.js`
- Modify: `services/ops_ui/src/anime_ops_ui/static/styles/components.css`
- Modify: `services/ops_ui/src/anime_ops_ui/static/styles/pages.css`
- Modify: `services/ops_ui/tests/test_shell_routes.py`
- Modify: `services/ops_ui/tests/test_contracts.py`

- [ ] **Step 1: Write failing SSR/contract assertions for the new section order**

Add assertions that the dashboard HTML now orders sections as:
1. broadcast wall
2. trends
3. host + network
4. pipeline
5. diagnostics

- [ ] **Step 2: Run the focused dashboard test and verify it fails**

Run:

```bash
/Users/sunzhuofan/RPI_Anime/.venv/bin/python -m pytest \
  services/ops_ui/tests/test_shell_routes.py::test_dashboard_shell_contains_bootstrap_roots \
  services/ops_ui/tests/test_contracts.py::test_overview_payload_matches_phase3_dashboard_app_contract -q
```

Expected: FAIL because the template still renders `Pipeline` before `Host + Network` and `Trends`.

- [ ] **Step 3: Reorder the dashboard sections in the template**

Update `services/ops_ui/src/anime_ops_ui/templates/dashboard.html` so the post-wall order is:
- `Trends`
- `Host + Network`
- `Pipeline`
- `Diagnostics`

- [ ] **Step 4: Change the pipeline renderer to a process-state treatment**

Update `services/ops_ui/src/anime_ops_ui/static/app.js` so pipeline cards render with a dedicated dashboard-specific template that emphasizes:
- label
- large value
- short detail
- a non-misleading visual rail/accent state

Do not fabricate percentage semantics.

- [ ] **Step 5: Update layout/styles for the new balance**

Update `services/ops_ui/src/anime_ops_ui/static/styles/components.css` and `services/ops_ui/src/anime_ops_ui/static/styles/pages.css` so:
- hero spacing is reduced
- `Trends` and `Host + Network` balance as a half-width row
- `Pipeline` becomes a full-width row with stronger visual rhythm and less text-wall feel

- [ ] **Step 6: Run focused UI contract tests**

Run:

```bash
/Users/sunzhuofan/RPI_Anime/.venv/bin/python -m pytest \
  services/ops_ui/tests/test_shell_routes.py \
  services/ops_ui/tests/test_contracts.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add services/ops_ui/src/anime_ops_ui/templates/dashboard.html \
  services/ops_ui/src/anime_ops_ui/static/app.js \
  services/ops_ui/src/anime_ops_ui/static/styles/components.css \
  services/ops_ui/src/anime_ops_ui/static/styles/pages.css \
  services/ops_ui/tests/test_shell_routes.py \
  services/ops_ui/tests/test_contracts.py
git commit -m "feat: rebalance dashboard sections and pipeline visuals"
```

---

### Task 4: Final Verification And Raspberry Pi Smoke

**Files:**
- Modify: none unless regressions are found
- Test: `services/ops_ui/tests/test_services.py`
- Test: `services/ops_ui/tests/test_dashboard_contract.py`
- Test: `services/ops_ui/tests/test_shell_routes.py`
- Test: `services/ops_ui/tests/test_contracts.py`

- [ ] **Step 1: Run the full ops-ui suite**

Run:

```bash
/Users/sunzhuofan/RPI_Anime/.venv/bin/python -m pytest services/ops_ui/tests -q
```

Expected: PASS.

- [ ] **Step 2: Run JS syntax verification**

Run:

```bash
node --check services/ops_ui/src/anime_ops_ui/static/app.js
node --check services/ops_ui/src/anime_ops_ui/static/shell.js
node --check services/ops_ui/src/anime_ops_ui/static/language.js
```

Expected: all commands exit 0.

- [ ] **Step 3: Sync to Raspberry Pi and rebuild**

Run:

```bash
PI_HOST=sunzhuofan.local PI_REMOTE_USER=sunzhuofan ./scripts/sync_to_pi.sh
PI_HOST=sunzhuofan.local ./scripts/remote_up.sh
```

- [ ] **Step 4: Run Raspberry Pi smoke checks**

Run:

```bash
ssh sunzhuofan.local "curl -s http://127.0.0.1:3000/healthz"
ssh sunzhuofan.local "curl -s --cookie 'anime-ops-ui-lang=en' http://127.0.0.1:3000/ | rg -n 'Broadcast Wall|ready in library|Pipeline|Trends'"
ssh sunzhuofan.local "curl -s --cookie 'anime-ops-ui-lang=zh-Hans' http://127.0.0.1:3000/api/overview | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d[\"summary_strip\"][0][\"answer\"])'"
```

Expected:
- health returns `{"ok":true}`
- English SSR reflects the new section order and compact controls
- Chinese overview summary answer matches the current count of `LIB`-outlined cards

- [ ] **Step 5: Commit only if fixes were needed**

If verification finds regressions, make the minimal fix and commit it with a focused message. If verification passes cleanly, do not create an extra no-op commit.

