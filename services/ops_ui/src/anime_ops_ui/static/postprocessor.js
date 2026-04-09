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
const {
  createPageBootstrap,
  escapeHtml,
  fetchJson,
  formatUpdatedLabel,
  metricTemplate,
  renderEmptyState,
} = window.AnimeOpsCore;

let postRefreshMs = 15000;
const POSTPROCESSOR_FALLBACK_COPY = {
  meta: {
    refresh_suffix: "s",
    details_summary: "Details",
    command_label: "Command",
  },
  status_badges: {
    ready: "READY",
    waiting: "WAITING",
    active: "ACTIVE",
    unparsed: "REVIEW",
    unknown: "UNKNOWN",
  },
  item_meta: {
    files: "files",
    completed: "completed",
  },
  field_labels: {
    best_overall: "Best Overall",
    best_completed: "Best Completed",
    candidates: "Candidates",
    completed: "Completed",
  },
  empty_section: {
    title: "No {section} items right now.",
    detail_fallback: "Wait for the next refresh.",
  },
  events_empty: {
    title: "No postprocessor events yet.",
    detail: "When the next watch pass or manual rerun happens, structured records will appear here.",
  },
  diagnostics: {
    source_fallback: "postprocessor",
    message_fallback: "Unavailable",
    unavailable_title: "Postprocessor unavailable",
  },
};

function formatTemplate(template, values) {
  return Object.entries(values).reduce(
    (result, [key, value]) => result.replaceAll(`{${key}}`, String(value)),
    String(template || "")
  );
}

function postprocessorCopy(payload) {
  return {
    meta: {
      refresh_suffix: payload.copy?.meta?.refresh_suffix || POSTPROCESSOR_FALLBACK_COPY.meta.refresh_suffix,
      details_summary:
        payload.copy?.meta?.details_summary || POSTPROCESSOR_FALLBACK_COPY.meta.details_summary,
      command_label: payload.copy?.meta?.command_label || POSTPROCESSOR_FALLBACK_COPY.meta.command_label,
    },
    status_badges: {
      ready: payload.copy?.status_badges?.ready || POSTPROCESSOR_FALLBACK_COPY.status_badges.ready,
      waiting: payload.copy?.status_badges?.waiting || POSTPROCESSOR_FALLBACK_COPY.status_badges.waiting,
      active: payload.copy?.status_badges?.active || POSTPROCESSOR_FALLBACK_COPY.status_badges.active,
      unparsed: payload.copy?.status_badges?.unparsed || POSTPROCESSOR_FALLBACK_COPY.status_badges.unparsed,
      unknown: payload.copy?.status_badges?.unknown || POSTPROCESSOR_FALLBACK_COPY.status_badges.unknown,
    },
    item_meta: {
      files: payload.copy?.item_meta?.files || POSTPROCESSOR_FALLBACK_COPY.item_meta.files,
      completed:
        payload.copy?.item_meta?.completed || POSTPROCESSOR_FALLBACK_COPY.item_meta.completed,
    },
    field_labels: {
      best_overall:
        payload.copy?.field_labels?.best_overall || POSTPROCESSOR_FALLBACK_COPY.field_labels.best_overall,
      best_completed:
        payload.copy?.field_labels?.best_completed || POSTPROCESSOR_FALLBACK_COPY.field_labels.best_completed,
      candidates:
        payload.copy?.field_labels?.candidates || POSTPROCESSOR_FALLBACK_COPY.field_labels.candidates,
      completed:
        payload.copy?.field_labels?.completed || POSTPROCESSOR_FALLBACK_COPY.field_labels.completed,
    },
    empty_section: {
      title: payload.copy?.empty_section?.title || POSTPROCESSOR_FALLBACK_COPY.empty_section.title,
      detail_fallback:
        payload.copy?.empty_section?.detail_fallback ||
        POSTPROCESSOR_FALLBACK_COPY.empty_section.detail_fallback,
    },
    events_empty: {
      title: payload.copy?.events_empty?.title || POSTPROCESSOR_FALLBACK_COPY.events_empty.title,
      detail: payload.copy?.events_empty?.detail || POSTPROCESSOR_FALLBACK_COPY.events_empty.detail,
    },
    diagnostics: {
      source_fallback:
        payload.copy?.diagnostics?.source_fallback || POSTPROCESSOR_FALLBACK_COPY.diagnostics.source_fallback,
      message_fallback:
        payload.copy?.diagnostics?.message_fallback ||
        POSTPROCESSOR_FALLBACK_COPY.diagnostics.message_fallback,
      unavailable_title:
        payload.copy?.diagnostics?.unavailable_title ||
        POSTPROCESSOR_FALLBACK_COPY.diagnostics.unavailable_title,
    },
  };
}

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

function logItemTemplate(item, copy) {
  const level = String(item.level || "info").toUpperCase();
  const source = String(item.source || copy.diagnostics.source_fallback);
  const action = String(item.action || "event");
  const details = item.details && Object.keys(item.details).length
    ? `<details class="log-details"><summary>${escapeHtml(copy.meta.details_summary)}</summary><pre>${escapeHtml(JSON.stringify(item.details, null, 2))}</pre></details>`
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

function commandTemplate(item, copy) {
  return `
    <article class="review-action-card">
      <div class="review-action-head">
        <div>
          <h3>${escapeHtml(item.label)}</h3>
          <p>${escapeHtml(item.description)}</p>
        </div>
      </div>
      <div class="review-action-meta">
        <span>${copy.meta.command_label}</span>
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

function queueItemTemplate(item, status, copy) {
  const badgeClass =
    status === "ready"
      ? "panel-badge"
      : status === "waiting"
        ? "panel-badge panel-badge-muted"
        : status === "active"
          ? "panel-badge panel-badge-muted"
          : "panel-badge panel-badge-muted";
  const statusLabel = copy.status_badges[status] || copy.status_badges.unknown;
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
          <span class="${badgeClass}">${escapeHtml(statusLabel)}</span>
          <h3>${escapeHtml(item.title || "-")}</h3>
          <span class="service-meta">${escapeHtml(item.reason || "-")}</span>
        </div>
        <div class="review-item-side">
          <span class="review-item-size">${escapeHtml(item.episode_label || `${item.media_count || 0} ${copy.item_meta.files}`)}</span>
          <span>${escapeHtml(item.candidate_count ? `${item.completed_count}/${item.candidate_count} ${copy.item_meta.completed}` : item.reason || "-")}</span>
        </div>
      </div>
      <div class="review-item-grid">
        <div>
          <span class="review-item-label">${copy.field_labels.best_overall}</span>
          <span class="review-item-value">${escapeHtml(item.best_overall || "-")}</span>
        </div>
        <div>
          <span class="review-item-label">${copy.field_labels.best_completed}</span>
          <span class="review-item-value">${escapeHtml(item.best_completed || "-")}</span>
        </div>
        <div>
          <span class="review-item-label">${copy.field_labels.candidates}</span>
          <span class="review-item-value">${escapeHtml(item.candidate_count ?? item.media_count ?? "-")}</span>
        </div>
        <div>
          <span class="review-item-label">${copy.field_labels.completed}</span>
          <span class="review-item-value">${escapeHtml(item.completed_count ?? 0)}</span>
        </div>
      </div>
      ${candidateList}
      ${unparsedMeta}
    </article>
  `;
}

function sectionTemplate(section, copy) {
  const items = section.items || [];
  const body = items.length
    ? items.map((item) => queueItemTemplate(item, section.id, copy)).join("")
    : `
      <div class="review-empty">
        <strong>${escapeHtml(formatTemplate(copy.empty_section.title, { section: section.title }))}</strong>
        <span>${escapeHtml(section.description || copy.empty_section.detail_fallback)}</span>
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
  const copy = postprocessorCopy(payload);
  postTitle.textContent = payload.title || "Postprocessor";
  postSubtitle.textContent = payload.subtitle || "";
  postUpdated.textContent = formatUpdatedLabel(cachedAt);
  postRefreshMs = (payload.refresh_interval_seconds || 15) * 1000;
  postRefresh.textContent = `${Math.round(postRefreshMs / 1000)}${copy.meta.refresh_suffix}`;
  postWorkerBadge.textContent = `${payload.worker_badge || "-"}`;

  postSummary.innerHTML = (payload.summary_cards || []).map(metricTemplate).join("");
  postConfig.innerHTML = (payload.config_cards || []).map(metricTemplate).join("");
  postCommands.innerHTML = (payload.commands || []).map((item) => commandTemplate(item, copy)).join("");
  postSections.innerHTML = (payload.sections || []).map((section) => sectionTemplate(section, copy)).join("");

  if (!payload.recent_events || !payload.recent_events.length) {
    postEvents.innerHTML = renderEmptyState(copy.events_empty.title, copy.events_empty.detail);
  } else {
    postEvents.innerHTML = payload.recent_events.map((item) => logItemTemplate(item, copy)).join("");
  }

  postFlash.innerHTML = (payload.diagnostics || [])
    .map((item) =>
      flashTemplate(
        item.source || copy.diagnostics.source_fallback,
        item.message || copy.diagnostics.message_fallback
      )
    )
    .join("");
}

const postprocessorPage = createPageBootstrap({
  cacheKey: POSTPROCESSOR_CACHE_KEY,
  fetcher: () => fetchJson("/api/postprocessor", { cache: "no-store" }),
  render,
  getIntervalMs: () => postRefreshMs,
  onError: (error) => {
    postFlash.innerHTML = flashTemplate(
      POSTPROCESSOR_FALLBACK_COPY.diagnostics.unavailable_title,
      error.message || String(error)
    );
  },
});

postprocessorPage.start();
