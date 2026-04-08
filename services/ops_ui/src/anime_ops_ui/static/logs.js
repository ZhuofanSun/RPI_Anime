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
const {
  clearFlash,
  createPageBootstrap,
  debounce,
  escapeHtml,
  fetchJson,
  formatUpdatedLabel,
  getQueryState,
  metricTemplate,
  renderEmptyState,
  setFlash,
  setQueryState,
} = window.AnimeOpsCore;

let logsRefreshMs = 10000;
let logsPayload = { items: [], levels: [], sources: [] };
const initialLogsState = getQueryState(["source", "level", "q"]);

function optionTemplate(values, label) {
  return [
    `<option value="">全部${label}</option>`,
    ...values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`),
  ].join("");
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
      ? `<details class="log-details"><summary>详细信息</summary><pre>${escapeHtml(JSON.stringify(item.details, null, 2))}</pre></details>`
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
  logsUpdated.textContent = formatUpdatedLabel();
  logsRefreshMs = (payload.refresh_interval_seconds || 10) * 1000;
  logsRefresh.textContent = `${Math.round(logsRefreshMs / 1000)}s`;
  logsRetentionBadge.textContent = `上限 ${payload.retention_cap || "-"}`;
  logsSummary.innerHTML = (payload.summary_cards || []).map(metricTemplate).join("");

  const sourceValue = logsSourceFilter.value || initialLogsState.source;
  const levelValue = logsLevelFilter.value || initialLogsState.level;
  logsSourceFilter.innerHTML = optionTemplate(payload.sources || [], "来源");
  logsLevelFilter.innerHTML = optionTemplate(payload.levels || [], "等级");
  if (sourceValue && Array.from(logsSourceFilter.options).some((option) => option.value === sourceValue)) {
    logsSourceFilter.value = sourceValue;
  }
  if (levelValue && Array.from(logsLevelFilter.options).some((option) => option.value === levelValue)) {
    logsLevelFilter.value = levelValue;
  }

  logsListMeta.textContent = `可见 ${payload.items.length} / 总计 ${payload.total_count}`;
  if (!payload.items.length) {
    logsList.innerHTML = renderEmptyState("当前没有匹配的日志。", "可以调整筛选条件，或者等待后台动作写入新的结构化事件。");
  } else {
    logsList.innerHTML = payload.items.map(logItemTemplate).join("");
  }
}

function syncUrlFromFilters() {
  setQueryState(
    {
      source: logsSourceFilter.value,
      level: logsLevelFilter.value,
      q: logsSearch.value.trim(),
    },
    ["source", "level", "q"]
  );
}

function buildLogsParams() {
  const params = new URLSearchParams();
  if (logsSourceFilter.value) params.set("source", logsSourceFilter.value);
  if (logsLevelFilter.value) params.set("level", logsLevelFilter.value);
  if (logsSearch.value.trim()) params.set("q", logsSearch.value.trim());
  params.set("limit", "300");
  return params;
}

const logsPage = createPageBootstrap({
  fetcher: () => fetchJson(`/api/logs?${buildLogsParams().toString()}`, { cache: "no-store" }),
  render: renderLogs,
  getIntervalMs: () => logsRefreshMs,
  onError: (error) => {
    setFlash("error", "日志页不可用", error.message || String(error));
  },
});

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
    setFlash("success", "日志已清理", payload.message || "日志已清理。");
    await logsPage.tick();
  } catch (error) {
    setFlash("error", "清理失败", error.message || String(error));
  }
}

const debouncedLogsRefresh = debounce(() => {
  syncUrlFromFilters();
  void logsPage.tick();
}, 220);

logsSourceFilter.addEventListener("change", () => {
  syncUrlFromFilters();
  void logsPage.tick();
});
logsLevelFilter.addEventListener("change", () => {
  syncUrlFromFilters();
  void logsPage.tick();
});
logsSearch.addEventListener("input", () => {
  clearFlash();
  debouncedLogsRefresh();
});
logsClear.addEventListener("click", clearLogs);

if (initialLogsState.source) logsSourceFilter.value = initialLogsState.source;
if (initialLogsState.level) logsLevelFilter.value = initialLogsState.level;
if (initialLogsState.q) logsSearch.value = initialLogsState.q;

logsPage.start();
