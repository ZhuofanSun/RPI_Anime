const logsTitle = document.getElementById("logs-title");
const logsSubtitle = document.getElementById("logs-subtitle");
const logsStorage = document.getElementById("logs-storage");
const logsUpdated = document.getElementById("logs-updated");
const logsRefresh = document.getElementById("logs-refresh");
const logsRetentionBadge = document.getElementById("logs-retention-badge");
const logsSummary = document.getElementById("logs-summary");
const logsSourceFilter = document.getElementById("logs-source-filter");
const logsLevelFilter = document.getElementById("logs-level-filter");
const logsSearch = document.getElementById("logs-search");
const logsListMeta = document.getElementById("logs-list-meta");
const logsList = document.getElementById("logs-list");
const logsClear = document.getElementById("logs-clear");
const logsFlash = document.getElementById("logs-flash");

let logsRefreshMs = 10000;
let logsTimerId = null;
let logsFetchInFlight = false;
let logsPayload = { items: [], levels: [], sources: [] };

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function metricTemplate(card) {
  return `
    <article class="metric-card">
      <span class="metric-label">${escapeHtml(card.label)}</span>
      <span class="metric-value">${escapeHtml(card.value)}</span>
      <span class="metric-detail">${escapeHtml(card.detail)}</span>
    </article>
  `;
}

function optionTemplate(values, label) {
  return [
    `<option value="">All ${label}</option>`,
    ...values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`),
  ].join("");
}

function flashTemplate(tone, title, message) {
  const cls =
    tone === "error"
      ? "flash-error"
      : tone === "warning"
        ? "flash-warning"
        : tone === "info"
          ? "flash-info"
          : "flash-success";
  return `
    <div class="flash-banner ${cls}">
      <strong>${escapeHtml(title)}</strong>
      <span>${escapeHtml(message)}</span>
    </div>
  `;
}

function setFlash(tone, title, message) {
  logsFlash.innerHTML = flashTemplate(tone, title, message);
}

function clearFlash() {
  logsFlash.innerHTML = "";
}

function levelTone(level) {
  switch ((level || "").toLowerCase()) {
    case "success":
      return "log-success";
    case "warning":
      return "log-warning";
    case "error":
      return "log-error";
    default:
      return "log-info";
  }
}

function logItemTemplate(item) {
  const level = String(item.level || "info").toUpperCase();
  const source = String(item.source || "unknown");
  const action = String(item.action || "event");
  const details = item.details && Object.keys(item.details).length
    ? `<details class="log-details"><summary>details</summary><pre>${escapeHtml(JSON.stringify(item.details, null, 2))}</pre></details>`
    : "";
  return `
    <article class="log-entry ${levelTone(item.level)}">
      <div class="log-entry-top">
        <div class="log-entry-main">
          <div class="log-entry-tags">
            <span class="log-tag log-tag-source">${escapeHtml(source)}</span>
            <span class="log-tag log-tag-level">${escapeHtml(level)}</span>
            <span class="log-tag log-tag-action">${escapeHtml(action)}</span>
          </div>
          <strong>${escapeHtml(item.message)}</strong>
        </div>
        <time class="log-entry-time">${escapeHtml(item.ts)}</time>
      </div>
      ${details}
    </article>
  `;
}

function renderLogs(payload) {
  logsPayload = payload;
  logsTitle.textContent = payload.title || "Logs";
  logsSubtitle.textContent = payload.subtitle || "";
  logsStorage.textContent = payload.storage_path || "-";
  logsUpdated.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  logsRefreshMs = (payload.refresh_interval_seconds || 10) * 1000;
  logsRefresh.textContent = `${Math.round(logsRefreshMs / 1000)}s`;
  logsRetentionBadge.textContent = `cap ${payload.retention_cap || "-"}`;
  logsSummary.innerHTML = (payload.summary_cards || []).map(metricTemplate).join("");

  const sourceValue = logsSourceFilter.value;
  const levelValue = logsLevelFilter.value;
  logsSourceFilter.innerHTML = optionTemplate(payload.sources || [], "sources");
  logsLevelFilter.innerHTML = optionTemplate(payload.levels || [], "levels");
  if (sourceValue && Array.from(logsSourceFilter.options).some((option) => option.value === sourceValue)) {
    logsSourceFilter.value = sourceValue;
  }
  if (levelValue && Array.from(logsLevelFilter.options).some((option) => option.value === levelValue)) {
    logsLevelFilter.value = levelValue;
  }

  logsListMeta.textContent = `${payload.items.length} visible / ${payload.total_count} total`;
  if (!payload.items.length) {
    logsList.innerHTML = `
      <div class="review-empty">
        <strong>当前没有匹配的日志。</strong>
        <span>可以调整筛选条件，或者等待后台动作写入新的结构化事件。</span>
      </div>
    `;
  } else {
    logsList.innerHTML = payload.items.map(logItemTemplate).join("");
  }
}

function scheduleRefresh() {
  if (logsTimerId) {
    clearTimeout(logsTimerId);
  }
  logsTimerId = window.setTimeout(() => {
    refreshLogs();
  }, logsRefreshMs);
}

async function refreshLogs() {
  if (logsFetchInFlight) return;
  logsFetchInFlight = true;
  try {
    const params = new URLSearchParams();
    if (logsSourceFilter.value) params.set("source", logsSourceFilter.value);
    if (logsLevelFilter.value) params.set("level", logsLevelFilter.value);
    if (logsSearch.value.trim()) params.set("q", logsSearch.value.trim());
    params.set("limit", "300");
    const response = await fetch(`/api/logs?${params.toString()}`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const payload = await response.json();
    renderLogs(payload);
  } catch (error) {
    setFlash("error", "Logs unavailable", error.message || String(error));
  } finally {
    logsFetchInFlight = false;
    scheduleRefresh();
  }
}

async function clearLogs() {
  if (!window.confirm("确认清理结构化日志？这个动作会清空当前 Logs 页里的历史记录。")) {
    return;
  }
  clearFlash();
  try {
    const response = await fetch("/api/logs/clear", { method: "POST" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const payload = await response.json();
    setFlash("success", "Logs cleared", payload.message || "日志已清理。");
    await refreshLogs();
  } catch (error) {
    setFlash("error", "Clear failed", error.message || String(error));
  }
}

logsSourceFilter.addEventListener("change", refreshLogs);
logsLevelFilter.addEventListener("change", refreshLogs);
logsSearch.addEventListener("input", () => {
  clearFlash();
  refreshLogs();
});
logsClear.addEventListener("click", clearLogs);

refreshLogs();
