const servicesGrid = document.getElementById("services-grid");
const trendGrid = document.getElementById("trend-grid");
const systemCards = document.getElementById("system-cards");
const queueCards = document.getElementById("queue-cards");
const networkCards = document.getElementById("network-cards");
const diagnostics = document.getElementById("diagnostics");
const pageTitle = document.getElementById("page-title");
const pageSubtitle = document.getElementById("page-subtitle");
const hostName = document.getElementById("host-name");
const lastUpdated = document.getElementById("last-updated");
const refreshIntervalLabel = document.getElementById("refresh-interval");

let refreshIntervalMs = 8000;
let refreshInFlight = false;
let refreshTimerId = null;

function serviceInitials(name) {
  return name
    .split(/\s+/)
    .map((part) => part[0] || "")
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function statusClass(status) {
  const normalized = (status || "unknown").replace(/\s+/g, "").toLowerCase();
  if (["running", "healthy", "online"].includes(normalized)) return "status-running";
  if (["starting", "restarting"].includes(normalized)) return "status-starting";
  if (["offline", "exited", "dead"].includes(normalized)) return "status-offline";
  return "status-unknown";
}

function statusLabel(status) {
  const normalized = (status || "unknown").replace(/-/g, " ");
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function metricTemplate(card) {
  return `
    <article class="metric-card">
      <span class="metric-label">${card.label}</span>
      <span class="metric-value">${card.value}</span>
      <span class="metric-detail">${card.detail}</span>
    </article>
  `;
}

function serviceTemplate(service) {
  const href = service.href || "#";
  const disabled = service.href ? "" : "disabled";
  const externalAttrs = service.href ? 'target="_blank" rel="noopener noreferrer"' : 'aria-disabled="true"';
  return `
    <article class="service-card">
      <div class="service-top">
        <div class="service-mark">${serviceInitials(service.name)}</div>
        <div class="status-pill ${statusClass(service.status)}" title="${service.status || "unknown"}">
          <span class="status-dot"></span>
          <span>${statusLabel(service.status)}</span>
        </div>
      </div>
      <div>
        <h3 class="service-name">${service.name}</h3>
        <p class="service-desc">${service.description}</p>
      </div>
      <div class="service-meta-wrap">
        <div class="service-meta">${service.meta || "-"}</div>
        <div class="service-uptime">${service.uptime || "-"}</div>
      </div>
      <div class="service-actions">
        <a class="service-link ${disabled}" href="${href}" ${externalAttrs}>
          ${service.href ? "Open Service" : "Coming Next"}
        </a>
      </div>
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
              <div class="trend-bar-track" title="${bar.label} · ${bar.value_label || rawValue}">
                <span class="trend-bar-fill" style="height: ${height}%"></span>
              </div>
              <span class="trend-bar-label">${bar.label}</span>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

function trendTemplate(card) {
  const toneClass = card.tone ? `trend-${card.tone}` : "trend-teal";
  const windowLabel = card.window_label ? `<span class="trend-window">${card.window_label}</span>` : "";
  let canvas = `<div class="trend-canvas trend-canvas-empty">No history yet.</div>`;

  if (card.chart_kind === "bars") {
    const bars = Array.isArray(card.bars) ? card.bars : [];
    canvas = `<div class="trend-canvas trend-canvas-bars">${barsTemplate(bars)}</div>`;
  } else {
    const points = Array.isArray(card.points) ? card.points : [];
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
          <span class="trend-label">${card.label}</span>
          <strong class="trend-value">${card.value}</strong>
        </div>
        <div class="trend-side">
          ${windowLabel}
          <span class="trend-detail">${card.detail}</span>
        </div>
      </div>
      ${canvas}
    </article>
  `;
}

function diagnosticsTemplate(items) {
  if (!items.length) {
    return `<div class="diagnostic-empty">All local data sources are responding.</div>`;
  }

  return items
    .map(
      (item) => `
      <article class="diagnostic-item">
        <span class="diagnostic-source">${item.source}</span>
        <p class="diagnostic-message">${item.message}</p>
      </article>
    `
    )
    .join("");
}

function scheduleRefresh() {
  if (refreshTimerId) {
    clearTimeout(refreshTimerId);
  }
  refreshTimerId = window.setTimeout(() => {
    refreshOverview();
  }, refreshIntervalMs);
}

async function refreshOverview() {
  if (refreshInFlight) {
    return;
  }
  refreshInFlight = true;
  try {
    const response = await fetch("/api/overview", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    pageTitle.textContent = data.title;
    pageSubtitle.textContent = data.subtitle;
    hostName.textContent = data.host;
    lastUpdated.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    refreshIntervalMs = (data.refresh_interval_seconds || 8) * 1000;
    refreshIntervalLabel.textContent = `Auto · ${Math.round(refreshIntervalMs / 1000)}s`;

    servicesGrid.innerHTML = data.services.map(serviceTemplate).join("");
    trendGrid.innerHTML = data.trend_cards.map(trendTemplate).join("");
    systemCards.innerHTML = data.system_cards.map(metricTemplate).join("");
    queueCards.innerHTML = data.queue_cards.map(metricTemplate).join("");
    networkCards.innerHTML = data.network_cards.map(metricTemplate).join("");
    diagnostics.innerHTML = diagnosticsTemplate(data.diagnostics || []);
  } catch (error) {
    diagnostics.innerHTML = diagnosticsTemplate([
      { source: "frontend", message: error.message || String(error) },
    ]);
  } finally {
    refreshInFlight = false;
    scheduleRefresh();
  }
}

refreshOverview();
