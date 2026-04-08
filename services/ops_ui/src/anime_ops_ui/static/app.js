const dashboardHero = document.getElementById("dashboard-hero");
const heroEyebrow = document.getElementById("dashboard-hero-eyebrow");
const heroTitle = document.getElementById("dashboard-hero-title");
const heroSummary = document.getElementById("dashboard-hero-summary");
const heroStatusPill = document.getElementById("dashboard-hero-status-pill");
const heroStatusLabel = document.getElementById("dashboard-hero-status-label");
const summaryStrip = document.getElementById("dashboard-summary-strip");
const pipelineGrid = document.getElementById("dashboard-pipeline-grid");
const statusGrid = document.getElementById("dashboard-status-grid");
const trendGrid = document.getElementById("dashboard-trend-grid");
const diagnostics = document.getElementById("diagnostics");
const hostName = document.getElementById("host-name");
const lastUpdated = document.getElementById("last-updated");
const refreshIntervalLabel = document.getElementById("refresh-interval");
const OVERVIEW_CACHE_KEY = "anime-ops-ui-overview-cache-v3";
const {
  createPageBootstrap,
  escapeHtml,
  fetchJson,
  formatUpdatedLabel,
  metricTemplate,
} = window.AnimeOpsCore;

let refreshIntervalMs = 8000;

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

function trendTemplate(card) {
  const tone = card?.tone || "teal";
  const toneClass = ["teal", "amber", "ocean", "violet"].includes(tone) ? `trend-${tone}` : "trend-teal";
  const windowLabel = card?.window_label ? `<span class="trend-window">${escapeHtml(card.window_label)}</span>` : "";
  let canvas = `<div class="trend-canvas trend-canvas-empty">No history yet.</div>`;

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

function diagnosticsTemplate(items) {
  if (!items.length) {
    return `<div class="diagnostic-empty">本地数据源响应正常。</div>`;
  }

  return items
    .map(
      (item) => `
      <article class="diagnostic-item">
        <span class="diagnostic-source">${escapeHtml(item?.source || "diagnostics")}</span>
        <p class="diagnostic-message">${escapeHtml(item?.message || "unknown issue")}</p>
      </article>
    `
    )
    .join("");
}

function renderOverview(data, { cachedAt } = {}) {
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
  refreshIntervalLabel.textContent = `Auto · ${Math.round(refreshIntervalMs / 1000)}s`;

  const summaryItems = Array.isArray(data.summary_strip) ? data.summary_strip : [];
  summaryStrip.innerHTML = summaryItems.map(summaryItemTemplate).join("");

  const pipelineCards = Array.isArray(data.pipeline_cards) ? data.pipeline_cards : [];
  pipelineGrid.innerHTML = pipelineCards.map(metricTemplate).join("");

  const statusCards = [...(Array.isArray(data.system_cards) ? data.system_cards : []), ...(Array.isArray(data.network_cards) ? data.network_cards : [])];
  statusGrid.innerHTML = statusCards.map(metricTemplate).join("");

  const trendCards = Array.isArray(data.trend_cards) ? data.trend_cards : [];
  trendGrid.innerHTML = trendCards.map(trendTemplate).join("");

  const diagnosticItems = Array.isArray(data.diagnostics) ? data.diagnostics : [];
  diagnostics.classList.remove("diagnostics-loading");
  diagnostics.classList.toggle("diagnostics-has-items", diagnosticItems.length > 0);
  diagnostics.innerHTML = diagnosticsTemplate(diagnosticItems);
}

const overviewPage = createPageBootstrap({
  cacheKey: OVERVIEW_CACHE_KEY,
  fetcher: () => fetchJson("/api/overview", { cache: "no-store" }),
  render: renderOverview,
  getIntervalMs: () => refreshIntervalMs,
  onError: (error) => {
    diagnostics.classList.remove("diagnostics-loading");
    diagnostics.classList.add("diagnostics-has-items");
    diagnostics.innerHTML = diagnosticsTemplate([
      { source: "frontend", message: error.message || String(error) },
    ]);
  },
});

overviewPage.start();
