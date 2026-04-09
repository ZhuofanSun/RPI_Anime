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
const LOGS_FALLBACK_COPY = {
  filters: {
    all_sources: "All Sources",
    all_levels: "All Levels",
    details_summary: "Details",
  },
  meta: {
    refresh_suffix: "s",
    retention_badge: "Cap {count}",
    list_meta: "Visible {visible} / Total {total}",
  },
  empty: {
    title: "No logs match the current filters.",
    detail: "Adjust the filters or wait for a new structured event to be written.",
  },
  status: {
    unavailable_title: "Logs unavailable",
    clear_failed_title: "Clear Failed",
  },
  clear: {
    confirm: "Clear the structured event log? This removes the current Logs history from the workspace.",
    success_title: "Logs Cleared",
    success_message: "Cleared {count} structured log entries.",
  },
};

function formatTemplate(template, values) {
  return Object.entries(values).reduce(
    (result, [key, value]) => result.replaceAll(`{${key}}`, String(value)),
    String(template || "")
  );
}

function logsCopy(payload) {
  return {
    filters: {
      all_sources: payload.copy?.filters?.all_sources || LOGS_FALLBACK_COPY.filters.all_sources,
      all_levels: payload.copy?.filters?.all_levels || LOGS_FALLBACK_COPY.filters.all_levels,
      details_summary: payload.copy?.filters?.details_summary || LOGS_FALLBACK_COPY.filters.details_summary,
    },
    meta: {
      refresh_suffix: payload.copy?.meta?.refresh_suffix || LOGS_FALLBACK_COPY.meta.refresh_suffix,
      retention_badge: payload.copy?.meta?.retention_badge || LOGS_FALLBACK_COPY.meta.retention_badge,
      list_meta: payload.copy?.meta?.list_meta || LOGS_FALLBACK_COPY.meta.list_meta,
    },
    empty: {
      title: payload.copy?.empty?.title || LOGS_FALLBACK_COPY.empty.title,
      detail: payload.copy?.empty?.detail || LOGS_FALLBACK_COPY.empty.detail,
    },
    status: {
      unavailable_title:
        payload.copy?.status?.unavailable_title || LOGS_FALLBACK_COPY.status.unavailable_title,
      clear_failed_title:
        payload.copy?.status?.clear_failed_title || LOGS_FALLBACK_COPY.status.clear_failed_title,
    },
    clear: {
      confirm: payload.copy?.clear?.confirm || LOGS_FALLBACK_COPY.clear.confirm,
      success_title: payload.copy?.clear?.success_title || LOGS_FALLBACK_COPY.clear.success_title,
      success_message:
        payload.copy?.clear?.success_message || LOGS_FALLBACK_COPY.clear.success_message,
    },
  };
}

function optionTemplate(values, label) {
  return [
    `<option value="">${escapeHtml(label)}</option>`,
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

function logItemTemplate(item, copy) {
  const level = String(item.level || "info").toUpperCase();
  const source = String(item.source || "unknown");
  const action = String(item.action || "event");
  const details = item.details && Object.keys(item.details).length
      ? `<details class="log-details"><summary>${escapeHtml(copy.filters.details_summary)}</summary><pre>${escapeHtml(JSON.stringify(item.details, null, 2))}</pre></details>`
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
  const copy = logsCopy(payload);
  logsPayload = payload;
  logsTitle.textContent = payload.title || "Logs";
  logsSubtitle.textContent = payload.subtitle || "";
  logsStorage.textContent = payload.storage_path || "-";
  logsUpdated.textContent = formatUpdatedLabel();
  logsRefreshMs = (payload.refresh_interval_seconds || 10) * 1000;
  logsRefresh.textContent = `${Math.round(logsRefreshMs / 1000)}${copy.meta.refresh_suffix}`;
  logsRetentionBadge.textContent = formatTemplate(copy.meta.retention_badge, { count: payload.retention_cap || "-" });
  logsSummary.innerHTML = (payload.summary_cards || []).map(metricTemplate).join("");

  const sourceValue = logsSourceFilter.value || initialLogsState.source;
  const levelValue = logsLevelFilter.value || initialLogsState.level;
  logsSourceFilter.innerHTML = optionTemplate(payload.sources || [], copy.filters.all_sources);
  logsLevelFilter.innerHTML = optionTemplate(payload.levels || [], copy.filters.all_levels);
  if (sourceValue && Array.from(logsSourceFilter.options).some((option) => option.value === sourceValue)) {
    logsSourceFilter.value = sourceValue;
  }
  if (levelValue && Array.from(logsLevelFilter.options).some((option) => option.value === levelValue)) {
    logsLevelFilter.value = levelValue;
  }

  logsListMeta.textContent = formatTemplate(copy.meta.list_meta, {
    visible: payload.items.length,
    total: payload.total_count,
  });
  if (!payload.items.length) {
    logsList.innerHTML = renderEmptyState(copy.empty.title, copy.empty.detail);
  } else {
    logsList.innerHTML = payload.items.map((item) => logItemTemplate(item, copy)).join("");
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
    setFlash(logsFlash, "error", logsCopy(logsPayload).status.unavailable_title, error.message || String(error));
  },
});

async function clearLogs() {
  const copy = logsCopy(logsPayload);
  if (!window.confirm(copy.clear.confirm)) {
    return;
  }
  clearFlash(logsFlash);
  try {
    const response = await fetch("/api/logs/clear", { method: "POST" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const result = await response.json();
    setFlash(
      logsFlash,
      "success",
      copy.clear.success_title,
      formatTemplate(copy.clear.success_message, { count: result.cleared || 0 })
    );
    await logsPage.tick();
  } catch (error) {
    setFlash(logsFlash, "error", copy.status.clear_failed_title, error.message || String(error));
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
  clearFlash(logsFlash);
  debouncedLogsRefresh();
});
logsClear.addEventListener("click", clearLogs);

if (initialLogsState.source) logsSourceFilter.value = initialLogsState.source;
if (initialLogsState.level) logsLevelFilter.value = initialLogsState.level;
if (initialLogsState.q) logsSearch.value = initialLogsState.q;

logsPage.start();
