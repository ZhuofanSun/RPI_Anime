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
const servicePanelFeedback = document.getElementById("service-panel-feedback");
const restartStackButton = document.getElementById("restart-stack-button");
const restartStackDetail = document.getElementById("restart-stack-detail");
const OVERVIEW_CACHE_KEY = "anime-ops-ui-overview-cache-v3";

let refreshIntervalMs = 8000;
let refreshInFlight = false;
let refreshTimerId = null;
let feedbackTimerId = null;

function serviceInitials(name) {
  return name
    .split(/\s+/)
    .map((part) => part[0] || "")
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function resolveServiceHref(service) {
  if (!service?.href) {
    return "#";
  }

  try {
    const currentUrl = new URL(window.location.href);
    const targetUrl = new URL(service.href, currentUrl);

    if (service.internal) {
      return `${currentUrl.origin}${targetUrl.pathname}${targetUrl.search}${targetUrl.hash}`;
    }

    targetUrl.protocol = currentUrl.protocol;
    targetUrl.hostname = currentUrl.hostname;
    targetUrl.port = targetUrl.port || currentUrl.port;
    return targetUrl.toString();
  } catch {
    return service.href;
  }
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

function showServiceFeedback(kind, message) {
  if (!servicePanelFeedback) return;
  if (feedbackTimerId) {
    window.clearTimeout(feedbackTimerId);
  }
  servicePanelFeedback.textContent = message;
  servicePanelFeedback.className = `inline-feedback inline-feedback-${kind || "info"}`;
  feedbackTimerId = window.setTimeout(() => {
    servicePanelFeedback.className = "inline-feedback is-hidden";
    servicePanelFeedback.textContent = "";
  }, 6000);
}

function setButtonBusy(button, busy, busyLabel = "处理中…") {
  if (!button) return;
  if (busy) {
    button.dataset.originalLabel = button.textContent;
    button.disabled = true;
    button.textContent = busyLabel;
    return;
  }
  button.disabled = false;
  if (button.dataset.originalLabel) {
    button.textContent = button.dataset.originalLabel;
    delete button.dataset.originalLabel;
  }
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  let payload = null;
  try {
    payload = await response.json();
  } catch {}
  if (!response.ok) {
    throw new Error(payload?.detail || payload?.message || `HTTP ${response.status}`);
  }
  return payload || {};
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
  const href = resolveServiceHref(service);
  const disabled = service.href ? "" : "disabled";
  const internal = Boolean(service.internal);
  const restartTarget = service.restart_target || "";
  const restartButton = restartTarget
    ? `
        <button
          class="action-button action-button-compact action-button-secondary service-restart-button"
          type="button"
          data-service-restart="${restartTarget}"
          data-service-name="${service.restart_name || service.name}"
          data-service-reload="${service.restart_requires_reload ? "true" : "false"}"
        >
          ${service.restart_label || "Restart"}
        </button>
      `
    : "";
  const linkAttrs = service.href
    ? internal
      ? ""
      : 'target="_blank" rel="noopener noreferrer"'
    : 'aria-disabled="true"';
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
        <a class="service-link ${disabled}" href="${href}" ${linkAttrs}>
          ${service.href ? (internal ? "Open Workspace" : "Open Service") : "Coming Next"}
        </a>
        ${restartButton}
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
    return `<div class="diagnostic-empty">本地数据源响应正常。</div>`;
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

function loadOverviewCache() {
  try {
    const raw = window.sessionStorage.getItem(OVERVIEW_CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || !parsed.data) return null;
    return parsed;
  } catch {
    return null;
  }
}

function saveOverviewCache(data) {
  try {
    window.sessionStorage.setItem(
      OVERVIEW_CACHE_KEY,
      JSON.stringify({
        cachedAt: Date.now(),
        data,
      })
    );
  } catch {}
}

function formatUpdatedLabel(cachedAt) {
  return new Date(cachedAt || Date.now()).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function renderOverview(data, { cachedAt } = {}) {
  pageTitle.textContent = data.title;
  pageSubtitle.textContent = data.subtitle;
  hostName.textContent = window.location.host || data.host;
  lastUpdated.textContent = formatUpdatedLabel(cachedAt);
  refreshIntervalMs = (data.refresh_interval_seconds || 8) * 1000;
  refreshIntervalLabel.textContent = `Auto · ${Math.round(refreshIntervalMs / 1000)}s`;
  if (restartStackDetail && data.stack_control?.detail) {
    restartStackDetail.textContent = data.stack_control.detail;
  }

  servicesGrid.innerHTML = data.services.map(serviceTemplate).join("");
  trendGrid.innerHTML = data.trend_cards.map(trendTemplate).join("");
  systemCards.innerHTML = data.system_cards.map(metricTemplate).join("");
  queueCards.innerHTML = data.queue_cards.map(metricTemplate).join("");
  networkCards.innerHTML = data.network_cards.map(metricTemplate).join("");
  diagnostics.innerHTML = diagnosticsTemplate(data.diagnostics || []);
}

async function handleServiceRestart(button) {
  const target = button.dataset.serviceRestart;
  const name = button.dataset.serviceName || target;
  const requiresReload = button.dataset.serviceReload === "true";
  const confirmMessage = requiresReload
    ? `将重启 ${name}，当前页面会短暂断开。继续吗？`
    : `将重启 ${name}。继续吗？`;
  if (!window.confirm(confirmMessage)) {
    return;
  }

  try {
    setButtonBusy(button, true, "Restarting…");
    const payload = await postJson("/api/services/restart", { target });
    showServiceFeedback("success", payload.message || `${name} 重启指令已发送。`);
    const reloadAfterSeconds = Number(payload.reload_after_seconds || 0);
    if (reloadAfterSeconds > 0 || requiresReload) {
      window.setTimeout(() => {
        window.location.reload();
      }, Math.max(reloadAfterSeconds, 5) * 1000);
      return;
    }
    window.setTimeout(() => {
      refreshOverview();
    }, 1600);
  } catch (error) {
    showServiceFeedback("error", error.message || `${name} 重启失败。`);
  } finally {
    setButtonBusy(button, false);
  }
}

async function handleRestartStack() {
  if (!restartStackButton) return;
  const confirmMessage =
    "将依次重启 Jellyfin、qBittorrent、AutoBangumi、Glances、Postprocessor 和 Ops UI，不包含 Tailscale。继续吗？";
  if (!window.confirm(confirmMessage)) {
    return;
  }

  try {
    setButtonBusy(restartStackButton, true, "Restarting…");
    const payload = await postJson("/api/services/restart-all");
    showServiceFeedback("warning", payload.message || "整套服务重启已安排。");
    const reloadAfterSeconds = Number(payload.reload_after_seconds || 8);
    window.setTimeout(() => {
      window.location.reload();
    }, Math.max(reloadAfterSeconds, 6) * 1000);
  } catch (error) {
    showServiceFeedback("error", error.message || "整套服务重启失败。");
  } finally {
    setButtonBusy(restartStackButton, false);
  }
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
    renderOverview(data);
    saveOverviewCache(data);
  } catch (error) {
    diagnostics.innerHTML = diagnosticsTemplate([
      { source: "frontend", message: error.message || String(error) },
    ]);
  } finally {
    refreshInFlight = false;
    scheduleRefresh();
  }
}

const cachedOverview = loadOverviewCache();
if (cachedOverview) {
  renderOverview(cachedOverview.data, { cachedAt: cachedOverview.cachedAt });
}

servicesGrid?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-service-restart]");
  if (!button) return;
  event.preventDefault();
  handleServiceRestart(button);
});

restartStackButton?.addEventListener("click", (event) => {
  event.preventDefault();
  handleRestartStack();
});

refreshOverview();
