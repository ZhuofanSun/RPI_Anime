const reviewItemTitle = document.getElementById("review-item-title");
const reviewItemSubtitle = document.getElementById("review-item-subtitle");
const reviewItemBucket = document.getElementById("review-item-bucket");
const reviewItemUpdated = document.getElementById("review-item-updated");
const reviewItemRefresh = document.getElementById("review-item-refresh");
const reviewItemSummary = document.getElementById("review-item-summary");
const reviewItemMeta = document.getElementById("review-item-meta");
const reviewItemSiblings = document.getElementById("review-item-siblings");
const reviewItemActions = document.getElementById("review-item-actions");
const reviewItemBreadcrumbs = document.getElementById("review-item-breadcrumbs");
const reviewItemActionStatus = document.getElementById("review-item-action-status");
const {
  createPageBootstrap,
  escapeHtml,
  fetchJson,
  formHasFocus,
  formatUpdatedLabel,
  metricTemplate,
  renderEmptyState,
} = window.AnimeOpsCore;

const REVIEW_FLASH_KEY = "anime-ops-ui-flash-v1";
const reviewItemParams = new URLSearchParams(window.location.search);
const reviewItemId = reviewItemParams.get("id");

let reviewItemRefreshMs = 15000;
let reviewItemActionInFlight = false;
let reviewItemManualDraft = null;
let reviewItemSuspendRefreshUntil = 0;
const REVIEW_DETAIL_FALLBACKS = {
  en: {
    fallback_title: "Review Detail",
    summary: {
      size: "Size",
      series: "Series",
      folder_hint: "Folder Hint",
      siblings: "Sibling Files",
      siblings_detail: "Same parent directory",
    },
    meta_labels: {
      reason: "Reason",
      filename: "Filename",
      relative_path: "Relative Path",
      series_season: "Series / Season",
      auto_parse: "Automatic Parse",
    },
    auto_parse: {
      parsed: "Ready to publish",
      unparsed: "Needs manual handling",
      fallback: "Automatic parse failed",
    },
    actions: {
      retry_parse: {
        title: "Retry Parse",
        badge_ready: "Ready",
        badge_disabled: "Unavailable",
        score: "Score",
        button: "Retry Parse and Publish",
        pending: "Retrying parse and publishing this file.",
        description_ready: "Automatic parse is ready and can publish directly to: {target_path}",
        description_exists: "Automatic parse resolved a target path, but it already exists: {target_path}",
        description_failed: "Automatic parse is still failing: {reason}",
      },
      manual_publish: {
        title: "Manual Publish",
        badge: "Override",
        description: "When automatic parse is unreliable, confirm the series name, season, and episode manually before publishing to the seasonal library.",
        title_label: "Series Name",
        title_placeholder: "Enter the published series name",
        season_label: "Season",
        episode_label: "Episode",
        button: "Publish to Seasonal Library",
        pending: "Publishing to the seasonal library with manual values.",
      },
      delete: {
        title: "Delete File",
        badge: "Danger",
        description: "Delete the current file directly from the manual review queue. It will not move into the library and no copy will be kept.",
        button: "Delete Current File",
        confirm_title: "Delete File",
        confirm_message: "Delete this file from the manual review queue? This removes the current file immediately.",
        pending: "Deleting the current file.",
      },
    },
    status: {
      processing_title: "Working",
      processing_message: "Running the requested action.",
      success_title: "Action Complete",
      success_message: "The action finished successfully.",
      failure_title: "Action Failed",
      empty_siblings_title: "No sibling files in this directory.",
      empty_siblings_detail: "This is the only media file under the current folder.",
      load_failed_title: "Failed to load review item details.",
      missing_id_title: "Missing Review Item ID.",
      missing_id_detail: "Open the detail view from the Ops Review list.",
    },
  },
};
let reviewItemCurrentCopy = REVIEW_DETAIL_FALLBACKS.en;

function formatTemplate(template, values) {
  return Object.entries(values).reduce(
    (result, [key, value]) => result.replaceAll(`{${key}}`, String(value)),
    String(template || "")
  );
}

function reviewDetailCopy(payload) {
  const fallback = REVIEW_DETAIL_FALLBACKS.en;
  return {
    fallback_title: payload.copy?.fallback_title || fallback.fallback_title,
    summary: {
      size: payload.copy?.summary?.size || fallback.summary.size,
      series: payload.copy?.summary?.series || fallback.summary.series,
      folder_hint: payload.copy?.summary?.folder_hint || fallback.summary.folder_hint,
      siblings: payload.copy?.summary?.siblings || fallback.summary.siblings,
      siblings_detail: payload.copy?.summary?.siblings_detail || fallback.summary.siblings_detail,
    },
    meta_labels: {
      reason: payload.copy?.meta_labels?.reason || fallback.meta_labels.reason,
      filename: payload.copy?.meta_labels?.filename || fallback.meta_labels.filename,
      relative_path: payload.copy?.meta_labels?.relative_path || fallback.meta_labels.relative_path,
      series_season: payload.copy?.meta_labels?.series_season || fallback.meta_labels.series_season,
      auto_parse: payload.copy?.meta_labels?.auto_parse || fallback.meta_labels.auto_parse,
    },
    auto_parse: {
      parsed: payload.copy?.auto_parse?.parsed || fallback.auto_parse.parsed,
      unparsed: payload.copy?.auto_parse?.unparsed || fallback.auto_parse.unparsed,
      fallback: payload.copy?.auto_parse?.fallback || fallback.auto_parse.fallback,
    },
    actions: {
      retry_parse: {
        title: payload.copy?.actions?.retry_parse?.title || fallback.actions.retry_parse.title,
        badge_ready: payload.copy?.actions?.retry_parse?.badge_ready || fallback.actions.retry_parse.badge_ready,
        badge_disabled:
          payload.copy?.actions?.retry_parse?.badge_disabled || fallback.actions.retry_parse.badge_disabled,
        score: payload.copy?.actions?.retry_parse?.score || fallback.actions.retry_parse.score,
        button: payload.copy?.actions?.retry_parse?.button || fallback.actions.retry_parse.button,
        pending: payload.copy?.actions?.retry_parse?.pending || fallback.actions.retry_parse.pending,
        description_ready:
          payload.copy?.actions?.retry_parse?.description_ready || fallback.actions.retry_parse.description_ready,
        description_exists:
          payload.copy?.actions?.retry_parse?.description_exists || fallback.actions.retry_parse.description_exists,
        description_failed:
          payload.copy?.actions?.retry_parse?.description_failed || fallback.actions.retry_parse.description_failed,
      },
      manual_publish: {
        title: payload.copy?.actions?.manual_publish?.title || fallback.actions.manual_publish.title,
        badge: payload.copy?.actions?.manual_publish?.badge || fallback.actions.manual_publish.badge,
        description:
          payload.copy?.actions?.manual_publish?.description || fallback.actions.manual_publish.description,
        title_label:
          payload.copy?.actions?.manual_publish?.title_label || fallback.actions.manual_publish.title_label,
        title_placeholder:
          payload.copy?.actions?.manual_publish?.title_placeholder ||
          fallback.actions.manual_publish.title_placeholder,
        season_label:
          payload.copy?.actions?.manual_publish?.season_label || fallback.actions.manual_publish.season_label,
        episode_label:
          payload.copy?.actions?.manual_publish?.episode_label || fallback.actions.manual_publish.episode_label,
        button: payload.copy?.actions?.manual_publish?.button || fallback.actions.manual_publish.button,
        pending: payload.copy?.actions?.manual_publish?.pending || fallback.actions.manual_publish.pending,
      },
      delete: {
        title: payload.copy?.actions?.delete?.title || fallback.actions.delete.title,
        badge: payload.copy?.actions?.delete?.badge || fallback.actions.delete.badge,
        description: payload.copy?.actions?.delete?.description || fallback.actions.delete.description,
        button: payload.copy?.actions?.delete?.button || fallback.actions.delete.button,
        confirm_title:
          payload.copy?.actions?.delete?.confirm_title || fallback.actions.delete.confirm_title,
        confirm_message:
          payload.copy?.actions?.delete?.confirm_message || fallback.actions.delete.confirm_message,
        pending: payload.copy?.actions?.delete?.pending || fallback.actions.delete.pending,
      },
    },
    status: {
      processing_title: payload.copy?.status?.processing_title || fallback.status.processing_title,
      processing_message: payload.copy?.status?.processing_message || fallback.status.processing_message,
      success_title: payload.copy?.status?.success_title || fallback.status.success_title,
      success_message: payload.copy?.status?.success_message || fallback.status.success_message,
      failure_title: payload.copy?.status?.failure_title || fallback.status.failure_title,
      empty_siblings_title:
        payload.copy?.status?.empty_siblings_title || fallback.status.empty_siblings_title,
      empty_siblings_detail:
        payload.copy?.status?.empty_siblings_detail || fallback.status.empty_siblings_detail,
      load_failed_title: payload.copy?.status?.load_failed_title || fallback.status.load_failed_title,
      missing_id_title: payload.copy?.status?.missing_id_title || fallback.status.missing_id_title,
      missing_id_detail: payload.copy?.status?.missing_id_detail || fallback.status.missing_id_detail,
    },
  };
}

function breadcrumbTemplate(items) {
  return items
    .map((item) => {
      if (!item.href) {
        return `<span class="hero-link-current">${escapeHtml(item.label)}</span>`;
      }
      return `<a class="hero-link" href="${escapeHtml(item.href)}">${escapeHtml(item.label)}</a>`;
    })
    .join('<span class="hero-link-sep">/</span>');
}

function siblingTemplate(item) {
  return `
    <article class="review-sibling-item ${item.is_current ? "current" : ""}">
      <div>
        <strong>${escapeHtml(item.filename)}</strong>
        <span>${escapeHtml(item.modified_label)}</span>
      </div>
      <span>${escapeHtml(item.size_label)}</span>
    </article>
  `;
}

function detailMetaTemplate(item, autoParse, copy) {
  const autoLabel = autoParse.status === "parsed" ? copy.auto_parse.parsed : copy.auto_parse.unparsed;
  const autoDetail =
    autoParse.status === "parsed"
      ? `${autoParse.parsed.title} · S${String(autoParse.parsed.season).padStart(2, "0")}E${String(autoParse.parsed.episode).padStart(2, "0")}`
      : autoParse.reason || copy.auto_parse.fallback;
  return `
    <div class="review-detail-card">
      <span class="review-item-label">${copy.meta_labels.reason}</span>
      <strong>${escapeHtml(item.reason)}</strong>
      <p>${escapeHtml(item.bucket_label || item.bucket)}</p>
    </div>
    <div class="review-detail-card">
      <span class="review-item-label">${copy.meta_labels.filename}</span>
      <code>${escapeHtml(item.filename)}</code>
    </div>
    <div class="review-detail-card">
      <span class="review-item-label">${copy.meta_labels.relative_path}</span>
      <code>${escapeHtml(item.relative_path)}</code>
    </div>
    <div class="review-detail-card">
      <span class="review-item-label">${copy.meta_labels.series_season}</span>
      <strong>${escapeHtml(item.series_name)}</strong>
      <p>${escapeHtml(item.season_label)}</p>
    </div>
    <div class="review-detail-card">
      <span class="review-item-label">${copy.meta_labels.auto_parse}</span>
      <strong>${escapeHtml(autoLabel)}</strong>
      <p>${escapeHtml(autoDetail)}</p>
    </div>
  `;
}

function actionStatusTemplate(tone, title, message) {
  const cls = tone === "error" ? "flash-error" : tone === "info" ? "flash-info" : "flash-success";
  return `
    <div class="flash-banner ${cls}">
      <strong>${escapeHtml(title)}</strong>
      <span>${escapeHtml(message)}</span>
    </div>
  `;
}

function setActionStatus(tone, title, message) {
  if (!reviewItemActionStatus) return;
  reviewItemActionStatus.innerHTML = actionStatusTemplate(tone, title, message);
}

function clearActionStatus() {
  if (!reviewItemActionStatus) return;
  reviewItemActionStatus.innerHTML = "";
}

function storeFlash(tone, title, message) {
  try {
    window.sessionStorage.setItem(
      REVIEW_FLASH_KEY,
      JSON.stringify({
        tone,
        title,
        message,
      })
    );
  } catch {}
}

function manualDefaults(payload) {
  const defaults = payload.manual_publish_defaults || { title: "", season: 1, episode: 1 };
  return reviewItemManualDraft
    ? {
        ...defaults,
        ...reviewItemManualDraft,
      }
    : defaults;
}

function actionsTemplate(payload) {
  const copy = reviewDetailCopy(payload);
  const autoParse = payload.auto_parse || { status: "unparsed", reason: copy.auto_parse.fallback };
  const defaults = manualDefaults(payload);
  const canRetry = autoParse.status === "parsed" && !autoParse.target_exists;
  const retryDescription =
    autoParse.status === "parsed"
      ? autoParse.target_exists
        ? formatTemplate(copy.actions.retry_parse.description_exists, { target_path: autoParse.target_path })
        : formatTemplate(copy.actions.retry_parse.description_ready, { target_path: autoParse.target_path })
      : formatTemplate(copy.actions.retry_parse.description_failed, {
          reason: autoParse.reason || copy.auto_parse.fallback,
        });
  return `
    <article class="review-action-card">
      <div class="review-action-head">
        <h3>${copy.actions.retry_parse.title}</h3>
        <span class="panel-badge ${canRetry ? "" : "panel-badge-muted"}">${canRetry ? copy.actions.retry_parse.badge_ready : copy.actions.retry_parse.badge_disabled}</span>
      </div>
      <p>${escapeHtml(retryDescription)}</p>
      ${
        autoParse.score_summary
          ? `<div class="review-action-meta"><span>${copy.actions.retry_parse.score}</span><code>${escapeHtml(autoParse.score_summary)}</code></div>`
          : ""
      }
      <div class="review-action-footer">
        <button class="action-button" type="button" data-review-action="retry-parse" ${canRetry ? "" : "disabled"}>
          ${copy.actions.retry_parse.button}
        </button>
      </div>
    </article>

    <article class="review-action-card">
      <div class="review-action-head">
        <h3>${copy.actions.manual_publish.title}</h3>
        <span class="panel-badge">${copy.actions.manual_publish.badge}</span>
      </div>
      <p>${copy.actions.manual_publish.description}</p>
      <form id="manual-publish-form" class="review-form">
        <label class="review-control review-control-wide">
          <span class="review-control-label">${copy.actions.manual_publish.title_label}</span>
          <input
            id="manual-title"
            class="review-input"
            type="text"
            value="${escapeHtml(defaults.title)}"
            placeholder="${escapeHtml(copy.actions.manual_publish.title_placeholder)}"
          />
        </label>
        <div class="review-form-grid">
          <label class="review-control">
            <span class="review-control-label">${copy.actions.manual_publish.season_label}</span>
            <input
              id="manual-season"
              class="review-input"
              type="number"
              min="1"
              max="99"
              value="${escapeHtml(defaults.season)}"
            />
          </label>
          <label class="review-control">
            <span class="review-control-label">${copy.actions.manual_publish.episode_label}</span>
            <input
              id="manual-episode"
              class="review-input"
              type="number"
              min="1"
              max="999"
              value="${escapeHtml(defaults.episode)}"
            />
          </label>
        </div>
        <div class="review-action-footer">
          <button class="action-button" type="submit">${copy.actions.manual_publish.button}</button>
        </div>
      </form>
    </article>

    <article class="review-action-card review-action-card-danger">
      <div class="review-action-head">
        <h3>${copy.actions.delete.title}</h3>
        <span class="panel-badge panel-badge-muted">${copy.actions.delete.badge}</span>
      </div>
      <p>${copy.actions.delete.description}</p>
      <div class="review-action-footer">
        <button class="action-button action-button-danger" type="button" data-review-action="delete">
          ${copy.actions.delete.button}
        </button>
      </div>
    </article>
  `;
}

function bindActionControls(payload) {
  const copy = reviewDetailCopy(payload);
  const titleInput = document.getElementById("manual-title");
  const seasonInput = document.getElementById("manual-season");
  const episodeInput = document.getElementById("manual-episode");
  const publishForm = document.getElementById("manual-publish-form");
  const retryButton = document.querySelector('[data-review-action="retry-parse"]');
  const deleteButton = document.querySelector('[data-review-action="delete"]');

  const syncDraft = () => {
    reviewItemSuspendRefreshUntil = Date.now() + 60000;
    reviewItemManualDraft = {
      title: titleInput?.value ?? "",
      season: Number(seasonInput?.value || 1),
      episode: Number(episodeInput?.value || 1),
    };
  };

  [titleInput, seasonInput, episodeInput].forEach((input) => {
    input?.addEventListener("focus", () => {
      reviewItemSuspendRefreshUntil = Date.now() + 60000;
    });
    input?.addEventListener("input", syncDraft);
  });

  retryButton?.addEventListener("click", async () => {
    await performAction("retry-parse", `/api/manual-review/item/retry-parse?id=${encodeURIComponent(reviewItemId)}`, {
      title: copy.actions.retry_parse.title,
      pendingMessage: copy.actions.retry_parse.pending,
    });
  });

  publishForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    syncDraft();
    await performAction("publish", `/api/manual-review/item/publish?id=${encodeURIComponent(reviewItemId)}`, {
      title: copy.actions.manual_publish.title,
      pendingMessage: copy.actions.manual_publish.pending,
      body: reviewItemManualDraft,
    });
  });

  deleteButton?.addEventListener("click", async () => {
    if (!window.confirm(copy.actions.delete.confirm_message)) {
      return;
    }
    await performAction("delete", `/api/manual-review/item/delete?id=${encodeURIComponent(reviewItemId)}`, {
      title: copy.actions.delete.confirm_title,
      pendingMessage: copy.actions.delete.pending,
    });
  });
}

async function parseActionError(response) {
  try {
    const payload = await response.json();
    if (payload && typeof payload.detail === "string") {
      return payload.detail;
    }
  } catch {}
  return `HTTP ${response.status}`;
}

async function performAction(action, url, { title, pendingMessage, body } = {}) {
  if (reviewItemActionInFlight) {
    return;
  }
  reviewItemActionInFlight = true;
  setActionStatus(
    "info",
    title || reviewItemCurrentCopy.status.processing_title,
    pendingMessage || reviewItemCurrentCopy.status.processing_message
  );
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) {
      throw new Error(await parseActionError(response));
    }
    const payload = await response.json();
    storeFlash(
      "success",
      title || reviewItemCurrentCopy.status.success_title,
      payload.message || reviewItemCurrentCopy.status.success_message
    );
    window.location.href = "/ops-review";
  } catch (error) {
    setActionStatus("error", title || reviewItemCurrentCopy.status.failure_title, error.message || String(error));
  } finally {
    reviewItemActionInFlight = false;
  }
}

function shouldDeferRefresh() {
  const manualForm = document.getElementById("manual-publish-form");
  return reviewItemActionInFlight || formHasFocus(manualForm) || Date.now() < reviewItemSuspendRefreshUntil;
}

function renderReviewItem(payload) {
  const item = payload.item;
  const copy = reviewDetailCopy(payload);
  reviewItemCurrentCopy = copy;
  const autoParse = payload.auto_parse || { status: "unparsed", reason: copy.auto_parse.fallback };

  if (!reviewItemManualDraft) {
    reviewItemManualDraft = { ...(payload.manual_publish_defaults || {}) };
  }

  reviewItemTitle.textContent = payload.title || copy.fallback_title;
  reviewItemSubtitle.textContent = item.filename;
  reviewItemBucket.textContent = item.bucket_label || item.bucket;
  reviewItemUpdated.textContent = formatUpdatedLabel();
  reviewItemRefreshMs = (payload.refresh_interval_seconds || 15) * 1000;
  reviewItemRefresh.textContent = `${Math.round(reviewItemRefreshMs / 1000)}s`;
  reviewItemBreadcrumbs.innerHTML = breadcrumbTemplate(payload.breadcrumbs || []);
  reviewItemSummary.innerHTML = [
    { label: copy.summary.size, value: item.size_label, detail: item.extension },
    { label: copy.summary.series, value: item.series_name, detail: item.season_label },
    { label: copy.summary.folder_hint, value: item.folder_hint, detail: item.modified_label },
    { label: copy.summary.siblings, value: String((payload.siblings || []).length), detail: copy.summary.siblings_detail },
  ]
    .map(metricTemplate)
    .join("");
  reviewItemMeta.innerHTML = detailMetaTemplate(item, autoParse, copy);
  reviewItemSiblings.innerHTML = (payload.siblings || []).length
    ? payload.siblings.map(siblingTemplate).join("")
    : renderEmptyState(copy.status.empty_siblings_title, copy.status.empty_siblings_detail);
  reviewItemActions.innerHTML = actionsTemplate(payload);
  bindActionControls(payload);
}

const reviewItemPage = createPageBootstrap({
  fetcher: () => fetchJson(`/api/manual-review/item?id=${encodeURIComponent(reviewItemId)}`, { cache: "no-store" }),
  render: renderReviewItem,
  getIntervalMs: () => reviewItemRefreshMs,
  shouldPause: shouldDeferRefresh,
  onError: (error) => {
    reviewItemMeta.innerHTML = renderEmptyState(
      reviewItemCurrentCopy.status.load_failed_title,
      error.message || String(error),
      "review-empty-error"
    );
  },
});

if (!reviewItemId) {
  reviewItemMeta.innerHTML = renderEmptyState(
    reviewItemCurrentCopy.status.missing_id_title,
    reviewItemCurrentCopy.status.missing_id_detail,
    "review-empty-error"
  );
} else {
  clearActionStatus();
  reviewItemPage.start();
}
