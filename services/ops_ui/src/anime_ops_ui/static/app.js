const dashboardHero = document.getElementById("dashboard-hero");
const heroEyebrow = document.getElementById("dashboard-hero-eyebrow");
const heroTitle = document.getElementById("dashboard-hero-title");
const heroSummary = document.getElementById("dashboard-hero-summary");
const heroStatusPill = document.getElementById("dashboard-hero-status-pill");
const heroStatusLabel = document.getElementById("dashboard-hero-status-label");
const summaryStrip = document.getElementById("dashboard-summary-strip");
const weeklyScheduleRoot = document.getElementById("dashboard-weekly-schedule");
const unknownScheduleRoot = document.getElementById("dashboard-unknown-schedule");
const pipelineGrid = document.getElementById("dashboard-pipeline-grid");
const statusGrid = document.getElementById("dashboard-status-grid");
const trendGrid = document.getElementById("dashboard-trend-grid");
const diagnostics = document.getElementById("diagnostics");
const hostName = document.getElementById("host-name");
const lastUpdated = document.getElementById("last-updated");
const refreshIntervalLabel = document.getElementById("refresh-interval");
const OVERVIEW_CACHE_KEY = "anime-ops-ui-overview-cache-v3";
const UNKNOWN_VISIBLE_LIMIT = 4;
const {
  createPageBootstrap,
  escapeHtml,
  fetchJson,
  formatUpdatedLabel,
  metricTemplate,
} = window.AnimeOpsCore;

let refreshIntervalMs = 8000;

function overviewCopy(data) {
  return {
    schedule: {
      tooltipLabels: {
        titleRaw: data.copy?.schedule?.tooltip_labels?.title_raw || "Original title",
        groupName: data.copy?.schedule?.tooltip_labels?.group_name || "Group",
        source: data.copy?.schedule?.tooltip_labels?.source || "Source",
        subtitle: data.copy?.schedule?.tooltip_labels?.subtitle || "Subtitles",
        dpi: data.copy?.schedule?.tooltip_labels?.dpi || "Quality",
        seasonLabel: data.copy?.schedule?.tooltip_labels?.season_label || "Season",
      },
      listSeparator: data.copy?.schedule?.list_separator || ", ",
      titleFallback: data.copy?.schedule?.title_fallback || "Unknown",
      libraryReady: data.copy?.schedule?.library_ready || "Added to library this week and ready to play",
      reviewNotePrefix: data.copy?.schedule?.review_note_prefix || "Review note",
      emptyDay: data.copy?.schedule?.empty_day || "No broadcast",
      emptyWeek: data.copy?.schedule?.empty_week || "No weekly schedule yet.",
      unknownLabelFallback: data.copy?.schedule?.unknown_label_fallback || "Unknown",
      unknownEmpty: data.copy?.schedule?.unknown_empty || "No unscheduled entries.",
      expandHidden: data.copy?.schedule?.expand_hidden || "Show +{count}",
      collapseHidden: data.copy?.schedule?.collapse_hidden || "Collapse",
    },
    refreshAutoPrefix: data.copy?.refresh_auto_prefix || "Auto",
    trendEmpty: data.copy?.trend_empty || "No history yet.",
    diagnostics: {
      empty: data.copy?.diagnostics?.empty || "All local data sources responded normally.",
      sourceFallback: data.copy?.diagnostics?.source_fallback || "diagnostics",
      messageFallback: data.copy?.diagnostics?.message_fallback || "unknown issue",
      frontendSource: data.copy?.diagnostics?.frontend_source || "frontend",
    },
  };
}

function toneStatusClass(tone) {
  if (tone === "teal") return "status-running";
  if (tone === "amber") return "status-starting";
  if (tone === "rose") return "status-offline";
  return "status-unknown";
}

function summaryItemTemplate(item) {
  const tone = (item?.tone || "teal").toLowerCase();
  const toneClass = ["teal", "amber", "rose"].includes(tone) ? `summary-${tone}` : "summary-neutral";
  return `
    <article class="summary-item ${toneClass}">
      <span class="summary-question">${escapeHtml(item?.question || "-")}</span>
      <strong class="summary-answer">${escapeHtml(item?.answer || "-")}</strong>
    </article>
  `;
}

function posterInitials(title) {
  const normalized = String(title || "").trim();
  if (!normalized) return "??";
  const words = normalized.split(/\s+/).filter(Boolean);
  if (words.length >= 2) {
    return `${words[0].slice(0, 1)}${words[1].slice(0, 1)}`.toUpperCase();
  }
  return Array.from(normalized).slice(0, 2).join("").toUpperCase();
}

function scheduleTooltipRows(item, copy) {
  const rows = [
    [copy.schedule.tooltipLabels.titleRaw, item?.detail?.title_raw],
    [copy.schedule.tooltipLabels.groupName, item?.detail?.group_name],
    [copy.schedule.tooltipLabels.source, item?.detail?.source],
    [copy.schedule.tooltipLabels.subtitle, item?.detail?.subtitle],
    [copy.schedule.tooltipLabels.dpi, item?.detail?.dpi],
    [copy.schedule.tooltipLabels.seasonLabel, item?.detail?.season_label],
  ];
  return rows.filter(([, value]) => Boolean(value));
}

function scheduleTooltipLabel(item, copy) {
  const title = item?.title || copy.schedule.titleFallback;
  const rows = scheduleTooltipRows(item, copy);
  const detailText = rows.map(([label, value]) => `${label} ${value}`).join(copy.schedule.listSeparator);
  const libraryText = item?.is_library_ready ? copy.schedule.libraryReady : "";
  const reviewText = item?.detail?.review_reason ? `${copy.schedule.reviewNotePrefix} ${item.detail.review_reason}` : "";
  return [title, detailText, libraryText, reviewText].filter(Boolean).join(copy.schedule.listSeparator);
}

function scheduleTooltipTemplate(item, copy) {
  const title = item?.title || copy.schedule.titleFallback;
  const rows = scheduleTooltipRows(item, copy);
  const rowsMarkup = rows.length
    ? `
      <dl class="schedule-poster-tooltip-meta">
        ${rows
          .map(
            ([label, value]) => `
              <div class="schedule-poster-tooltip-row">
                <dt>${escapeHtml(label)}</dt>
                <dd>${escapeHtml(value || "-")}</dd>
              </div>
            `
          )
          .join("")}
      </dl>
    `
    : "";
  const libraryMarkup = item?.is_library_ready
    ? `<p class="schedule-poster-tooltip-state">${escapeHtml(copy.schedule.libraryReady)}</p>`
    : "";
  const reviewMarkup = item?.detail?.review_reason
    ? `<p class="schedule-poster-tooltip-note">${escapeHtml(copy.schedule.reviewNotePrefix)}: ${escapeHtml(item.detail.review_reason)}</p>`
    : "";

  return `
    <div class="schedule-poster-tooltip" role="note">
      <strong class="schedule-poster-tooltip-title">${escapeHtml(title)}</strong>
      ${rowsMarkup}
      ${libraryMarkup}
      ${reviewMarkup}
    </div>
  `;
}

function schedulePosterTemplate(item, copy) {
  const title = item?.title || copy.schedule.titleFallback;
  const stateClass = item?.is_library_ready ? " is-library-ready" : "";
  const tooltipMarkup = scheduleTooltipTemplate(item, copy);
  const ariaLabel = scheduleTooltipLabel(item, copy) || title;

  return `
    <article class="schedule-poster-card${stateClass}" tabindex="0" aria-label="${escapeHtml(ariaLabel)}">
      <div class="schedule-poster-media">
        ${
          item?.poster_url
            ? `<img class="schedule-poster-image" src="${escapeHtml(item.poster_url)}" alt="${escapeHtml(title)}" loading="lazy" referrerpolicy="no-referrer" />`
            : `<span class="schedule-poster-fallback">${escapeHtml(posterInitials(title))}</span>`
        }
      </div>
      ${tooltipMarkup}
    </article>
  `;
}

function scheduleDayColumnTemplate(day, todayWeekday, copy) {
  const items = Array.isArray(day?.items) ? day.items : [];
  const hiddenItems = Array.isArray(day?.hidden_items) ? day.hidden_items : [];
  const hasHiddenItems = Boolean(day?.has_hidden_items && hiddenItems.length > 0);
  const total = items.length + hiddenItems.length;
  const dayNumber = Number.isInteger(day?.weekday) ? day.weekday : -1;
  const hiddenId = `schedule-day-hidden-${dayNumber}`;
  const isToday = dayNumber === todayWeekday || day?.is_today;

  return `
    <article class="broadcast-day-column ${isToday ? "is-today" : ""}">
      <div class="broadcast-day-head">
        <span class="broadcast-day-label">${escapeHtml(day?.label || "?")}</span>
        <span class="broadcast-day-count">${total}</span>
      </div>
      ${
        items.length
          ? `<div class="schedule-poster-grid">${items.map((item) => schedulePosterTemplate(item, copy)).join("")}</div>`
          : `<div class="broadcast-empty">${escapeHtml(copy.schedule.emptyDay)}</div>`
      }
      ${
        hasHiddenItems
          ? `
        <button
          class="schedule-collapse-toggle"
          type="button"
          data-schedule-toggle
          aria-controls="${hiddenId}"
          aria-expanded="false"
          data-expand-label="${escapeHtml(copy.schedule.expandHidden.replace("{count}", hiddenItems.length))}"
          data-collapse-label="${escapeHtml(copy.schedule.collapseHidden)}"
        >${escapeHtml(copy.schedule.expandHidden.replace("{count}", hiddenItems.length))}</button>
        <div id="${hiddenId}" class="schedule-hidden-posters" hidden>
          <div class="schedule-poster-grid">${hiddenItems.map((item) => schedulePosterTemplate(item, copy)).join("")}</div>
        </div>
      `
          : ""
      }
    </article>
  `;
}

function unknownScheduleTemplate(unknown, copy) {
  const items = Array.isArray(unknown?.items) ? unknown.items : [];
  const hiddenItems = Array.isArray(unknown?.hidden_items) ? unknown.hidden_items : [];
  const visibleItems = items.slice(0, UNKNOWN_VISIBLE_LIMIT);
  const overflowItems = items.slice(UNKNOWN_VISIBLE_LIMIT);
  const mergedHiddenItems = [...overflowItems, ...hiddenItems];
  const hasHiddenItems = Boolean((unknown?.has_hidden_items && hiddenItems.length > 0) || mergedHiddenItems.length > 0);
  const total = items.length + hiddenItems.length;
  const hiddenId = "schedule-unknown-hidden";

  return `
    <div class="broadcast-unknown-head">
      <div class="broadcast-unknown-copy">
        <strong>${escapeHtml(unknown?.label || copy.schedule.unknownLabelFallback)}</strong>
      </div>
      <span class="broadcast-day-count">${total}</span>
    </div>
    ${
      visibleItems.length
        ? `<div class="schedule-poster-grid schedule-poster-grid-unknown">${visibleItems.map((item) => schedulePosterTemplate(item, copy)).join("")}</div>`
        : `<div class="broadcast-empty">${escapeHtml(copy.schedule.unknownEmpty)}</div>`
    }
    ${
      hasHiddenItems
        ? `
      <button
        class="schedule-collapse-toggle"
        type="button"
        data-schedule-toggle
        aria-controls="${hiddenId}"
        aria-expanded="false"
        data-expand-label="${escapeHtml(copy.schedule.expandHidden.replace("{count}", mergedHiddenItems.length))}"
        data-collapse-label="${escapeHtml(copy.schedule.collapseHidden)}"
      >${escapeHtml(copy.schedule.expandHidden.replace("{count}", mergedHiddenItems.length))}</button>
      <div id="${hiddenId}" class="schedule-hidden-posters" hidden>
        <div class="schedule-poster-grid schedule-poster-grid-unknown">${mergedHiddenItems.map((item) => schedulePosterTemplate(item, copy)).join("")}</div>
      </div>
    `
        : ""
    }
  `;
}

function bindScheduleToggles(container) {
  if (!container || container.dataset.toggleBound === "1") {
    return;
  }

  container.addEventListener("click", (event) => {
    const toggle = event.target.closest("[data-schedule-toggle]");
    if (!toggle) {
      return;
    }

    const controlsId = toggle.getAttribute("aria-controls");
    if (!controlsId) {
      return;
    }

    const target = document.getElementById(controlsId);
    if (!target) {
      return;
    }

    const isExpanded = toggle.getAttribute("aria-expanded") === "true";
    const nextExpanded = !isExpanded;
    toggle.setAttribute("aria-expanded", String(nextExpanded));
    toggle.textContent = nextExpanded ? toggle.dataset.collapseLabel || "Collapse" : toggle.dataset.expandLabel || "Show";
    target.hidden = !nextExpanded;
  });

  container.dataset.toggleBound = "1";
}

function sparklinePath(points, width = 260, height = 74, padding = 6) {
  if (!points.length) {
    return "";
  }

  const numeric = points.map((value) => Number(value) || 0);
  const min = Math.min(...numeric);
  const max = Math.max(...numeric);
  const range = max - min || 1;

  return numeric
    .map((value, index) => {
      const x = padding + (index / Math.max(numeric.length - 1, 1)) * (width - padding * 2);
      const y = height - padding - ((value - min) / range) * (height - padding * 2);
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

function barsTemplate(bars) {
  const values = bars.map((item) => Number(item.value) || 0);
  const max = Math.max(...values, 1);

  return `
    <div class="trend-bars">
      ${bars
        .map((bar) => {
          const rawValue = Number(bar.value) || 0;
          const height = max > 0 ? Math.max((rawValue / max) * 100, rawValue > 0 ? 8 : 3) : 3;
          return `
            <div class="trend-bar-col">
              <div class="trend-bar-track" title="${escapeHtml(`${bar.label || "-"} · ${bar.value_label || rawValue}`)}">
                <span class="trend-bar-fill" style="height: ${height}%"></span>
              </div>
              <span class="trend-bar-label">${escapeHtml(bar.label || "-")}</span>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

function trendTemplate(card, copy) {
  const tone = card?.tone || "teal";
  const toneClass = ["teal", "amber", "ocean", "violet"].includes(tone) ? `trend-${tone}` : "trend-teal";
  const windowLabel = card?.window_label ? `<span class="trend-window">${escapeHtml(card.window_label)}</span>` : "";
  let canvas = `<div class="trend-canvas trend-canvas-empty">${escapeHtml(copy.trendEmpty)}</div>`;

  if (card?.chart_kind === "bars") {
    const bars = Array.isArray(card.bars) ? card.bars : [];
    canvas = `<div class="trend-canvas trend-canvas-bars">${barsTemplate(bars)}</div>`;
  } else {
    const points = Array.isArray(card?.points) ? card.points : [];
    const path = sparklinePath(points);
    canvas = `
      <div class="trend-canvas">
        <svg viewBox="0 0 260 74" preserveAspectRatio="none" aria-hidden="true">
          <path class="trend-area" d="${path ? `${path} L 254 68 L 6 68 Z` : ""}"></path>
          <path class="trend-line" d="${path}"></path>
        </svg>
      </div>
    `;
  }

  return `
    <article class="trend-card ${toneClass}">
      <div class="trend-head">
        <div>
          <span class="trend-label">${escapeHtml(card?.label || "-")}</span>
          <strong class="trend-value">${escapeHtml(card?.value || "-")}</strong>
        </div>
        <div class="trend-side">
          ${windowLabel}
          <span class="trend-detail">${escapeHtml(card?.detail || "-")}</span>
        </div>
      </div>
      ${canvas}
    </article>
  `;
}

function pipelineCardTone(index) {
  return ["teal", "amber", "ocean", "violet", "rose"][index % 5];
}

function pipelineCardTemplate(card, index) {
  const tone = pipelineCardTone(index);
  const mark = posterInitials(card?.label || card?.value || String(index + 1));

  return `
    <article class="metric-card metric-card-pipeline metric-card-pipeline-${tone}">
      <div class="metric-card-visual" aria-hidden="true">
        <span class="metric-card-mark">${escapeHtml(mark)}</span>
        <span class="metric-card-ribbon"></span>
      </div>
      <div class="metric-card-copy">
        <span class="metric-label">${escapeHtml(card?.label || "-")}</span>
        <strong class="metric-value">${escapeHtml(card?.value || "-")}</strong>
        <span class="metric-detail">${escapeHtml(card?.detail || "-")}</span>
      </div>
    </article>
  `;
}

function diagnosticsTemplate(items, copy) {
  if (!items.length) {
    return `<div class="diagnostic-empty">${escapeHtml(copy.diagnostics.empty)}</div>`;
  }

  return items
    .map(
      (item) => `
      <article class="diagnostic-item">
        <span class="diagnostic-source">${escapeHtml(item?.source || copy.diagnostics.sourceFallback)}</span>
        <p class="diagnostic-message">${escapeHtml(item?.message || copy.diagnostics.messageFallback)}</p>
      </article>
    `
    )
    .join("");
}

function renderOverview(data, { cachedAt } = {}) {
  const copy = overviewCopy(data);
  if (dashboardHero) {
    dashboardHero.classList.remove("is-loading-state");
  }

  const heroTone = data.hero?.status_tone || "teal";
  if (heroEyebrow) heroEyebrow.textContent = data.hero?.eyebrow || "Control Surface";
  if (heroTitle) heroTitle.textContent = data.hero?.title || "RPI Anime Ops";
  if (heroSummary) heroSummary.textContent = data.hero?.summary || "";
  if (heroStatusPill) {
    heroStatusPill.className = `status-pill ${toneStatusClass(heroTone)}`;
  }
  if (heroStatusLabel) {
    heroStatusLabel.textContent = data.hero?.status_label || "Unknown";
  }

  hostName.textContent = window.location.host || data.hero?.host || "-";
  lastUpdated.textContent = formatUpdatedLabel(cachedAt);
  refreshIntervalMs = (data.refresh_interval_seconds || 8) * 1000;
  refreshIntervalLabel.textContent = `${copy.refreshAutoPrefix} · ${Math.round(refreshIntervalMs / 1000)}s`;

  const summaryItems = Array.isArray(data.summary_strip) ? data.summary_strip : [];
  summaryStrip.innerHTML = summaryItems.map(summaryItemTemplate).join("");

  const todayWeekday = Number(data.weekly_schedule?.today_weekday);
  const weeklyDays = Array.isArray(data.weekly_schedule?.days) ? data.weekly_schedule.days : [];
  const unknownSchedule = data.weekly_schedule?.unknown || {};
  if (weeklyScheduleRoot) {
    weeklyScheduleRoot.innerHTML = weeklyDays.length
      ? weeklyDays.map((day) => scheduleDayColumnTemplate(day, todayWeekday, copy)).join("")
      : `<div class="broadcast-empty">${escapeHtml(copy.schedule.emptyWeek)}</div>`;
    bindScheduleToggles(weeklyScheduleRoot);
  }
  if (unknownScheduleRoot) {
    unknownScheduleRoot.classList.remove("is-loading-state");
    unknownScheduleRoot.innerHTML = unknownScheduleTemplate(unknownSchedule, copy);
    bindScheduleToggles(unknownScheduleRoot);
  }

  const pipelineCards = Array.isArray(data.pipeline_cards) ? data.pipeline_cards : [];
  pipelineGrid.innerHTML = pipelineCards.map((card, index) => pipelineCardTemplate(card, index)).join("");

  const statusCards = [...(Array.isArray(data.system_cards) ? data.system_cards : []), ...(Array.isArray(data.network_cards) ? data.network_cards : [])];
  statusGrid.innerHTML = statusCards.map(metricTemplate).join("");

  const trendCards = Array.isArray(data.trend_cards) ? data.trend_cards : [];
  trendGrid.innerHTML = trendCards.map((card) => trendTemplate(card, copy)).join("");

  const diagnosticItems = Array.isArray(data.diagnostics) ? data.diagnostics : [];
  diagnostics.classList.remove("diagnostics-loading");
  diagnostics.classList.toggle("diagnostics-has-items", diagnosticItems.length > 0);
  diagnostics.innerHTML = diagnosticsTemplate(diagnosticItems, copy);
}

const overviewPage = createPageBootstrap({
  cacheKey: OVERVIEW_CACHE_KEY,
  fetcher: () => fetchJson("/api/overview", { cache: "no-store" }),
  render: renderOverview,
  getIntervalMs: () => refreshIntervalMs,
  onError: (error) => {
    const copy = overviewCopy({ copy: {} });
    diagnostics.classList.remove("diagnostics-loading");
    diagnostics.classList.add("diagnostics-has-items");
    diagnostics.innerHTML = diagnosticsTemplate([{ source: copy.diagnostics.frontendSource, message: error.message || String(error) }], copy);
  },
});

overviewPage.start();
