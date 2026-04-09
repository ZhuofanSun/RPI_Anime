# Ops UI Dashboard Density Polish Design

Date: 2026-04-08
Branch baseline: `main`
Scope: post-phase-5 dashboard and shared-shell polish only

## Goal

Tighten the dashboard so the top control surface is less vertically heavy, make theme/language controls feel like compact utility toggles instead of a mini settings card, align the "今天有什么值得看" summary with the actual number of library-ready posters in the weekly wall, and rebalance the `Trends / Pipeline / Host + Network` area so it is less text-dominant.

This is a UI/layout follow-up on top of phase 5. It does not add new backend integrations, does not change the weekly schedule data model, and does not introduce new user actions.

## Approved Direction

The approved direction is **Option A: Compact Hero + Trends Left**.

That means:

1. The dashboard hero becomes shorter and less stacked.
2. Theme and language controls become two compact segmented controls aligned to the right.
3. The first summary-strip answer becomes a direct count of weekly-schedule cards that currently render with the `LIB` outline.
4. `Trends` moves into the upper half-width row beside `Host + Network`.
5. `Pipeline` moves below that row and becomes visually process-oriented instead of reading like three dense text cards.

## Scope

### In scope

- Shared preference control restyle for all pages
- Dashboard hero spacing and control alignment
- Summary-strip count logic for the first item
- Dashboard section ordering changes
- Pipeline visual treatment changes
- Host + Network compaction where needed for balance
- Contract and route tests needed to lock the new behavior

### Out of scope

- New backend data sources
- New dashboard sections
- Broadcast wall behavior changes beyond count derivation
- Phase 6 feature work
- Major visual redesign of non-dashboard pages beyond the shared preference control

## Shared Preferences

The current shared preference block reads like a small settings card and takes too much vertical room in every hero.

### New behavior

- Keep the same functionality and cookies.
- Remove the visible `Preferences` header and row-style chrome.
- Render the controls as two compact segmented groups:
  - theme: `浅 / 深` or `Light / Dark`
  - language: `中 / EN`
- Place the two groups on the far right of the hero meta area on all pages.
- On narrow widths they may wrap, but they should still read as a lightweight utility strip rather than a boxed settings module.

### Design constraints

- No emoji or icon-only controls.
- Keep clear focus-visible states.
- Preserve existing ARIA labels and reduced-motion behavior.
- Avoid making the controls look like primary actions.

## Dashboard Hero

### Current issue

The hero is too tall because status, meta pills, and preferences stack into a heavy right column.

### New layout

- Keep the left side as `eyebrow + title + short summary`.
- Keep the right side as:
  - status pill row
  - compact meta row with host, updated time, refresh, and the two compact preference groups
- Reduce vertical spacing between hero elements.
- Preserve the current visual direction and overall shell language.

## Summary Strip

### Current issue

The first summary item does not read as a concrete reflection of what the weekly wall visually shows.

### New rule

The first summary item answer must equal the total number of schedule items in the current weekly snapshot whose cards render with the `LIB` outline.

This count includes:

- all visible day-column items
- all hidden day-column overflow items
- all visible unknown-row items
- all hidden unknown-row overflow items

This count does not attempt to mean "today only". It is intentionally a wall-level "worth watching now" count because that is what the highlight language communicates visually.

### Display copy

- zh-Hans answer format: `{count} 部已入库，可播放`
- en answer format: `{count} ready in library`

The question label can remain the existing localized wording for now.

## Section Ordering

### New order after Broadcast Wall

1. `Trends` on the left
2. `Host + Network` on the right
3. `Pipeline` as a full-width row below them
4. `Diagnostics` unchanged below

### Reasoning

- `Trends` provides visual mass through charts, which balances the row better.
- `Host + Network` is structurally quieter and can sit opposite charts without feeling empty.
- `Pipeline` currently feels like "another set of text cards"; moving it to its own row gives it room to become more process-like.

## Pipeline Visual Treatment

### Current issue

Pipeline and Host + Network both currently read as groups of metric cards with mostly text. That makes the middle of the page feel repetitive and visually flat.

### New treatment

Pipeline should become a row of horizontal process-state cards instead of a standard metric-card grid.

Each pipeline item should emphasize:

- a strong label
- one large numeric/state value
- one short supporting detail
- a visual rail, accent band, or process marker that makes it feel operational rather than report-like

### Important constraint

Do not invent fake percentages or progress semantics that the data cannot justify. The visual treatment should communicate process/state, not misleading quantitative completion.

That means the preferred treatment is:

- accent rails
- strong value hierarchy
- compact supporting detail
- tone/color distinction by card purpose

and not:

- arbitrary progress bars based on guessed denominators

## Host + Network

Host + Network should stay denser and quieter than Pipeline.

### Recommended treatment

- keep compact system cards
- slightly tighten spacing and copy density if needed
- let this section read as a status board, not a second "feature row"

The section should feel visually lighter than Trends while still balancing the row through structure and card rhythm.

## Responsive Behavior

- Desktop keeps the new `Trends + Host/Network` row and full-width Pipeline row.
- Tablet may collapse the row into a single-column stack if needed.
- Mobile keeps the current single-column behavior, with preference controls wrapping cleanly.

## Data / Contract Notes

No new API endpoint is required.

Implementation should derive the library-ready count from the existing overview payload's weekly schedule snapshot rather than adding a second backend-only count source. This avoids drift between the summary strip and the wall.

If implementation proves cleaner with a server-supplied count, that is acceptable only if it is derived from the exact same weekly-schedule snapshot used to render the wall.

## Testing

### Required checks

- shared preference controls still render once per page
- locale switching still updates the compact controls correctly
- first summary item count matches the number of `LIB`-outlined cards in the payload contract
- dashboard section order is locked by shell/template coverage
- existing overview payload and page-script tests still pass

### Manual validation

- desktop and mobile widths
- light and dark theme contrast
- zh-Hans and English
- real Raspberry Pi deployment on `sunzhuofan.local`

## Risks

### Risk: summary semantics feel slightly broader than the label

Accepted for this follow-up. The answer intentionally mirrors visible wall highlights rather than true "today only" semantics.

### Risk: pipeline restyle becomes decorative instead of useful

Mitigation: keep the value and supporting detail prominent; do not hide the operational numbers behind visual flair.

### Risk: compact preferences become too subtle

Mitigation: keep active states, focus states, and segmentation clear even after removing the heavier card chrome.

