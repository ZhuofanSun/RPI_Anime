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

const REVIEW_FLASH_KEY = "anime-ops-ui-flash-v1";
const reviewItemParams = new URLSearchParams(window.location.search);
const reviewItemId = reviewItemParams.get("id");

let reviewItemRefreshMs = 15000;
let reviewItemTimerId = null;
let reviewItemLoading = false;
let reviewItemActionInFlight = false;
let reviewItemManualDraft = null;

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

function detailMetaTemplate(item, autoParse) {
  const autoLabel = autoParse.status === "parsed" ? "可直接发布" : "需要人工处理";
  const autoDetail =
    autoParse.status === "parsed"
      ? `${autoParse.parsed.title} · S${String(autoParse.parsed.season).padStart(2, "0")}E${String(autoParse.parsed.episode).padStart(2, "0")}`
      : autoParse.reason || "自动解析失败";
  return `
    <div class="review-detail-card">
      <span class="review-item-label">原因</span>
      <strong>${escapeHtml(item.reason)}</strong>
      <p>${escapeHtml(item.bucket)}</p>
    </div>
    <div class="review-detail-card">
      <span class="review-item-label">文件名</span>
      <code>${escapeHtml(item.filename)}</code>
    </div>
    <div class="review-detail-card">
      <span class="review-item-label">相对路径</span>
      <code>${escapeHtml(item.relative_path)}</code>
    </div>
    <div class="review-detail-card">
      <span class="review-item-label">作品 / Season</span>
      <strong>${escapeHtml(item.series_name)}</strong>
      <p>${escapeHtml(item.season_label)}</p>
    </div>
    <div class="review-detail-card">
      <span class="review-item-label">自动解析</span>
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
  const autoParse = payload.auto_parse || { status: "unparsed", reason: "自动解析失败" };
  const defaults = manualDefaults(payload);
  const canRetry = autoParse.status === "parsed" && !autoParse.target_exists;
  const retryDescription =
    autoParse.status === "parsed"
      ? autoParse.target_exists
        ? `自动解析命中了目标路径，但目标已存在：${autoParse.target_path}`
        : `自动解析已准备好，可直接发布到：${autoParse.target_path}`
      : `当前自动解析失败：${autoParse.reason || "无法稳定解析标题或季集信息"}`;
  return `
    <article class="review-action-card">
      <div class="review-action-head">
        <h3>重试解析</h3>
        <span class="panel-badge ${canRetry ? "" : "panel-badge-muted"}">${canRetry ? "可执行" : "不可执行"}</span>
      </div>
      <p>${escapeHtml(retryDescription)}</p>
      ${
        autoParse.score_summary
          ? `<div class="review-action-meta"><span>评分</span><code>${escapeHtml(autoParse.score_summary)}</code></div>`
          : ""
      }
      <div class="review-action-footer">
        <button class="action-button" type="button" data-review-action="retry-parse" ${canRetry ? "" : "disabled"}>
          重试解析并发布
        </button>
      </div>
    </article>

    <article class="review-action-card">
      <div class="review-action-head">
        <h3>手动发布</h3>
        <span class="panel-badge">覆盖发布</span>
      </div>
      <p>当自动解析不稳定时，手动确认剧名、季号和集号，再直接发布到季度库。</p>
      <form id="manual-publish-form" class="review-form">
        <label class="review-control review-control-wide">
          <span class="review-control-label">作品名</span>
          <input
            id="manual-title"
            class="review-input"
            type="text"
            value="${escapeHtml(defaults.title)}"
            placeholder="输入发布后的剧名"
          />
        </label>
        <div class="review-form-grid">
          <label class="review-control">
            <span class="review-control-label">Season</span>
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
            <span class="review-control-label">Episode</span>
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
          <button class="action-button" type="submit">发布到季度库</button>
        </div>
      </form>
    </article>

    <article class="review-action-card review-action-card-danger">
      <div class="review-action-head">
        <h3>删除文件</h3>
        <span class="panel-badge panel-badge-muted">危险操作</span>
      </div>
      <p>从人工审核队列中直接删除当前文件。这个动作不会移到媒体库，也不会保留副本。</p>
      <div class="review-action-footer">
        <button class="action-button action-button-danger" type="button" data-review-action="delete">
          删除当前文件
        </button>
      </div>
    </article>
  `;
}

function bindActionControls(payload) {
  const titleInput = document.getElementById("manual-title");
  const seasonInput = document.getElementById("manual-season");
  const episodeInput = document.getElementById("manual-episode");
  const publishForm = document.getElementById("manual-publish-form");
  const retryButton = document.querySelector('[data-review-action="retry-parse"]');
  const deleteButton = document.querySelector('[data-review-action="delete"]');

  const syncDraft = () => {
    reviewItemManualDraft = {
      title: titleInput?.value ?? "",
      season: Number(seasonInput?.value || 1),
      episode: Number(episodeInput?.value || 1),
    };
  };

  [titleInput, seasonInput, episodeInput].forEach((input) => {
    input?.addEventListener("input", syncDraft);
  });

  retryButton?.addEventListener("click", async () => {
    await performAction("retry-parse", `/api/manual-review/item/retry-parse?id=${encodeURIComponent(reviewItemId)}`, {
      title: "重试解析",
      pendingMessage: "正在重新解析并发布当前文件。",
    });
  });

  publishForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    syncDraft();
    await performAction("publish", `/api/manual-review/item/publish?id=${encodeURIComponent(reviewItemId)}`, {
      title: "手动发布",
      pendingMessage: "正在按手动参数发布到季度库。",
      body: reviewItemManualDraft,
    });
  });

  deleteButton?.addEventListener("click", async () => {
    if (!window.confirm("确认从人工审核队列删除这个文件？这个动作会直接删掉当前文件。")) {
      return;
    }
    await performAction("delete", `/api/manual-review/item/delete?id=${encodeURIComponent(reviewItemId)}`, {
      title: "删除文件",
      pendingMessage: "正在删除当前文件。",
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
  setActionStatus("info", title || "处理中", pendingMessage || "正在执行动作。");
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
    storeFlash("success", title || "操作已完成", payload.message || "动作已完成。");
    window.location.href = "/ops-review";
  } catch (error) {
    setActionStatus("error", title || "操作失败", error.message || String(error));
  } finally {
    reviewItemActionInFlight = false;
  }
}

function scheduleRefresh() {
  if (reviewItemTimerId) {
    clearTimeout(reviewItemTimerId);
  }
  reviewItemTimerId = window.setTimeout(() => {
    refreshReviewItem();
  }, reviewItemRefreshMs);
}

async function refreshReviewItem() {
  if (!reviewItemId || reviewItemLoading || reviewItemActionInFlight) {
    return;
  }
  reviewItemLoading = true;
  try {
    const response = await fetch(`/api/manual-review/item?id=${encodeURIComponent(reviewItemId)}`, {
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    const item = payload.item;
    const autoParse = payload.auto_parse || { status: "unparsed", reason: "自动解析失败" };

    if (!reviewItemManualDraft) {
      reviewItemManualDraft = { ...(payload.manual_publish_defaults || {}) };
    }

    reviewItemTitle.textContent = payload.title || "审核项详情";
    reviewItemSubtitle.textContent = item.filename;
    reviewItemBucket.textContent = item.bucket;
    reviewItemUpdated.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    reviewItemRefreshMs = (payload.refresh_interval_seconds || 15) * 1000;
    reviewItemRefresh.textContent = `${Math.round(reviewItemRefreshMs / 1000)}s`;
    reviewItemBreadcrumbs.innerHTML = breadcrumbTemplate(payload.breadcrumbs || []);
    reviewItemSummary.innerHTML = [
      { label: "大小", value: item.size_label, detail: item.extension },
      { label: "作品", value: item.series_name, detail: item.season_label },
      { label: "目录提示", value: item.folder_hint, detail: item.modified_label },
      { label: "同目录文件", value: String((payload.siblings || []).length), detail: "同一父目录" },
    ]
      .map(metricTemplate)
      .join("");
    reviewItemMeta.innerHTML = detailMetaTemplate(item, autoParse);
    reviewItemSiblings.innerHTML = (payload.siblings || []).length
      ? payload.siblings.map(siblingTemplate).join("")
      : `<div class="review-empty"><strong>当前没有同目录文件。</strong><span>当前目录下只有这一个媒体文件。</span></div>`;
    reviewItemActions.innerHTML = actionsTemplate(payload);
    bindActionControls(payload);
  } catch (error) {
    reviewItemMeta.innerHTML = `
      <div class="review-empty review-empty-error">
        <strong>加载审核项详情失败。</strong>
        <span>${escapeHtml(error.message || String(error))}</span>
      </div>
    `;
  } finally {
    reviewItemLoading = false;
    scheduleRefresh();
  }
}

if (!reviewItemId) {
  reviewItemMeta.innerHTML = `
    <div class="review-empty review-empty-error">
      <strong>缺少审核项 ID。</strong>
      <span>请从 Ops Review 列表页进入详情页。</span>
    </div>
  `;
} else {
  clearActionStatus();
  refreshReviewItem();
}
