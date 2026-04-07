const postTitle = document.getElementById("post-title");
const postSubtitle = document.getElementById("post-subtitle");
const postWorkerBadge = document.getElementById("post-worker-badge");
const postUpdated = document.getElementById("post-updated");
const postRefresh = document.getElementById("post-refresh");
const postSummary = document.getElementById("post-summary");
const postConfig = document.getElementById("post-config");
const postCommands = document.getElementById("post-commands");
const postSections = document.getElementById("post-sections");
const postEvents = document.getElementById("post-events");
const postFlash = document.getElementById("post-flash");
const POSTPROCESSOR_CACHE_KEY = "anime-ops-ui-postprocessor-cache-v1";
const { escapeHtml, formatUpdatedLabel, metricTemplate, readSessionCache, renderEmptyState, writeSessionCache } = window.AnimeOpsCore;

let postRefreshMs = 15000;
let postTimerId = null;
let postFetchInFlight = false;

function flashTemplate(title, message) {
  return `
    <div class="flash-banner flash-error">
      <strong>${escapeHtml(title)}</strong>
      <span>${escapeHtml(message)}</span>
    </div>
  `;
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
  const source = String(item.source || "postprocessor");
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

function commandTemplate(item) {
  return `
    <article class="review-action-card">
      <div class="review-action-head">
        <div>
          <h3>${escapeHtml(item.label)}</h3>
          <p>${escapeHtml(item.description)}</p>
        </div>
      </div>
      <div class="review-action-meta">
        <span>Command</span>
        <code>${escapeHtml(item.command)}</code>
      </div>
    </article>
  `;
}

function candidateTagTemplate(item) {
  return `
    <span class="post-candidate-chip ${item.completed ? "post-candidate-chip-complete" : ""}">
      <strong>${escapeHtml(item.progress_label)}</strong>
      <span>${escapeHtml(item.state)}</span>
      <span>${escapeHtml(item.score_summary)}</span>
    </span>
  `;
}

function queueItemTemplate(item, status) {
  const badgeClass =
    status === "ready"
      ? "panel-badge"
      : status === "waiting"
        ? "panel-badge panel-badge-muted"
        : status === "active"
          ? "panel-badge panel-badge-muted"
          : "panel-badge panel-badge-muted";
  const candidateList = item.candidates && item.candidates.length
    ? `<div class="post-candidate-list">${item.candidates.map(candidateTagTemplate).join("")}</div>`
    : "";
  const unparsedMeta = item.media_count
    ? `<div class="review-item-paths"><code>${escapeHtml(item.path || "-")}</code></div>`
    : "";

  return `
    <article class="review-item">
      <div class="review-item-top">
        <div class="review-item-heading">
          <span class="${badgeClass}">${escapeHtml((status || "unknown").toUpperCase())}</span>
          <h3>${escapeHtml(item.title || "-")}</h3>
          <span class="service-meta">${escapeHtml(item.reason || "-")}</span>
        </div>
        <div class="review-item-side">
          <span class="review-item-size">${escapeHtml(item.episode_label || `${item.media_count || 0} files`)}</span>
          <span>${escapeHtml(item.candidate_count ? `${item.completed_count}/${item.candidate_count} completed` : item.reason || "-")}</span>
        </div>
      </div>
      <div class="review-item-grid">
        <div>
          <span class="review-item-label">Best Overall</span>
          <span class="review-item-value">${escapeHtml(item.best_overall || "-")}</span>
        </div>
        <div>
          <span class="review-item-label">Best Completed</span>
          <span class="review-item-value">${escapeHtml(item.best_completed || "-")}</span>
        </div>
        <div>
          <span class="review-item-label">Candidates</span>
          <span class="review-item-value">${escapeHtml(item.candidate_count ?? item.media_count ?? "-")}</span>
        </div>
        <div>
          <span class="review-item-label">Completed</span>
          <span class="review-item-value">${escapeHtml(item.completed_count ?? 0)}</span>
        </div>
      </div>
      ${candidateList}
      ${unparsedMeta}
    </article>
  `;
}

function sectionTemplate(section) {
  const items = section.items || [];
  const body = items.length
    ? items.map((item) => queueItemTemplate(item, section.id)).join("")
    : `
      <div class="review-empty">
        <strong>当前没有 ${escapeHtml(section.title)} 条目。</strong>
        <span>${escapeHtml(section.description || "等待下一轮刷新。")}</span>
      </div>
    `;
  return `
    <section class="post-section">
      <div class="panel-head panel-head-compact">
        <div class="panel-heading">
          <h2>${escapeHtml(section.title)}</h2>
          <p>${escapeHtml(section.description || "")}</p>
        </div>
        <span class="panel-badge panel-badge-muted">${escapeHtml(section.meta || "-")}</span>
      </div>
      <div class="review-list">
        ${body}
      </div>
    </section>
  `;
}

function render(payload, { cachedAt } = {}) {
  postTitle.textContent = payload.title || "Postprocessor";
  postSubtitle.textContent = payload.subtitle || "";
  postUpdated.textContent = formatUpdatedLabel(cachedAt);
  postRefreshMs = (payload.refresh_interval_seconds || 15) * 1000;
  postRefresh.textContent = `${Math.round(postRefreshMs / 1000)}s`;
  const workerCard = (payload.summary_cards || []).find((item) => item.label === "Worker");
  postWorkerBadge.textContent = `${workerCard?.value || "-"}`;

  postSummary.innerHTML = (payload.summary_cards || []).map(metricTemplate).join("");
  postConfig.innerHTML = (payload.config_cards || []).map(metricTemplate).join("");
  postCommands.innerHTML = (payload.commands || []).map(commandTemplate).join("");
  postSections.innerHTML = (payload.sections || []).map(sectionTemplate).join("");

  if (!payload.recent_events || !payload.recent_events.length) {
    postEvents.innerHTML = renderEmptyState("还没有 postprocessor 事件。", "等下一轮 watch 处理下载或人工重跑后，这里会出现结构化记录。");
  } else {
    postEvents.innerHTML = payload.recent_events.map(logItemTemplate).join("");
  }

  postFlash.innerHTML = (payload.diagnostics || []).map((item) => flashTemplate(item.source || "postprocessor", item.message || "Unavailable")).join("");
}

function scheduleRefresh() {
  if (postTimerId) clearTimeout(postTimerId);
  postTimerId = window.setTimeout(() => {
    refreshPostprocessor();
  }, postRefreshMs);
}

async function refreshPostprocessor() {
  if (postFetchInFlight) return;
  postFetchInFlight = true;
  try {
    const response = await fetch("/api/postprocessor", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    writeSessionCache(POSTPROCESSOR_CACHE_KEY, payload);
    render(payload);
  } catch (error) {
    postFlash.innerHTML = flashTemplate("Postprocessor unavailable", error.message || String(error));
  } finally {
    postFetchInFlight = false;
    scheduleRefresh();
  }
}

const cached = readSessionCache(POSTPROCESSOR_CACHE_KEY);
if (cached?.payload) {
  render(cached.payload, { cachedAt: cached.cachedAt });
}
refreshPostprocessor();
