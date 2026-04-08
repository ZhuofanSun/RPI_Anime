const dashboardHero = document.getElementById("dashboard-hero");
const heroEyebrow = document.getElementById("dashboard-hero-eyebrow");
const heroTitle = document.getElementById("dashboard-hero-title");
const heroSummary = document.getElementById("dashboard-hero-summary");
const heroStatusPill = document.getElementById("dashboard-hero-status-pill");
const heroStatusLabel = document.getElementById("dashboard-hero-status-label");
const summaryStrip = document.getElementById("dashboard-summary-strip");
const serviceRowsRoot = document.getElementById("dashboard-service-rows");
const pipelineGrid = document.getElementById("dashboard-pipeline-grid");
const statusGrid = document.getElementById("dashboard-status-grid");
const trendGrid = document.getElementById("dashboard-trend-grid");
const diagnostics = document.getElementById("diagnostics");
const hostName = document.getElementById("host-name");
const lastUpdated = document.getElementById("last-updated");
const refreshIntervalLabel = document.getElementById("refresh-interval");
const servicePanelFeedback = document.getElementById("service-panel-feedback");
const restartStackButton = document.getElementById("restart-stack-button");
const restartStackDetail = document.getElementById("restart-stack-detail");
const OVERVIEW_CACHE_KEY = "anime-ops-ui-overview-cache-v3";
const {
  createPageBootstrap,
  escapeHtml,
  fetchJson,
  formatUpdatedLabel,
  metricTemplate,
} = window.AnimeOpsCore;

let refreshIntervalMs = 8000;
let feedbackTimerId = null;

function serviceInitials(name) {
  return String(name || "")
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

function toneStatusClass(tone) {
  if (tone === "teal") return "status-running";
  if (tone === "amber") return "status-starting";
  if (tone === "rose") return "status-offline";
  return "status-unknown";
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

function serviceRowTemplate(service) {
  const href = resolveServiceHref(service);
  const disabled = service?.href ? "" : "disabled";
  const internal = Boolean(service?.internal);
  const restartTarget = service?.restart_target || "";
  const restartButton = restartTarget
    ? `
        <button
          class="action-button action-button-compact action-button-secondary service-restart-button"
          type="button"
          data-service-restart="${escapeHtml(restartTarget)}"
          data-service-name="${escapeHtml(service?.restart_name || service?.name || restartTarget)}"
          data-service-reload="${service?.restart_requires_reload ? "true" : "false"}"
        >
          ${escapeHtml(service?.restart_label || "Restart")}
        </button>
      `
    : "";
  const linkAttrs = service?.href
    ? internal
      ? ""
      : 'target="_blank" rel="noopener noreferrer"'
    : 'aria-disabled="true"';

  return `
    <article class="service-row">
      <div class="service-row-status">
        <div class="service-mark">${escapeHtml(serviceInitials(service?.name || ""))}</div>
        <div class="service-row-main">
          <strong class="service-name">${escapeHtml(service?.name || "Unknown Service")}</strong>
          <span class="service-meta">${escapeHtml(service?.meta || "-")}</span>
        </div>
      </div>
      <div class="service-row-health">
        <span class="status-pill ${statusClass(service?.status)}" title="${escapeHtml(service?.status || "unknown")}">
          <span class="status-dot"></span>
          <span>${escapeHtml(statusLabel(service?.status))}</span>
        </span>
        <span class="service-uptime">${escapeHtml(service?.uptime || "-")}</span>
      </div>
      <div class="service-row-actions">
        <a class="service-link ${disabled}" href="${escapeHtml(href)}" ${linkAttrs}>
          ${service?.href ? (internal ? "Open Workspace" : "Open Service") : "暂不可用"}
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

  if (restartStackButton && data.stack_control?.label) {
    restartStackButton.textContent = data.stack_control.label;
  }
  if (restartStackDetail && data.stack_control?.detail) {
    restartStackDetail.textContent = data.stack_control.detail;
  }

  const summaryItems = Array.isArray(data.summary_strip) ? data.summary_strip : [];
  summaryStrip.innerHTML = summaryItems.map(summaryItemTemplate).join("");

  const serviceRows = Array.isArray(data.service_rows) ? data.service_rows : [];
  serviceRowsRoot.innerHTML = serviceRows.map(serviceRowTemplate).join("");

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
      void overviewPage.tick();
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

serviceRowsRoot?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-service-restart]");
  if (!button) return;
  event.preventDefault();
  handleServiceRestart(button);
});

restartStackButton?.addEventListener("click", (event) => {
  event.preventDefault();
  handleRestartStack();
});

overviewPage.start();
