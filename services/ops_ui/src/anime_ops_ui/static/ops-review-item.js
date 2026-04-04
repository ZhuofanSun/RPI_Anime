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

const reviewItemParams = new URLSearchParams(window.location.search);
const reviewItemId = reviewItemParams.get("id");
let reviewItemRefreshMs = 15000;
let reviewItemTimerId = null;
let reviewItemLoading = false;

function metricTemplate(card) {
  return `
    <article class="metric-card">
      <span class="metric-label">${card.label}</span>
      <span class="metric-value">${card.value}</span>
      <span class="metric-detail">${card.detail}</span>
    </article>
  `;
}

function breadcrumbTemplate(items) {
  return items
    .map((item) => {
      if (!item.href) {
        return `<span class="hero-link-current">${item.label}</span>`;
      }
      return `<a class="hero-link" href="${item.href}">${item.label}</a>`;
    })
    .join('<span class="hero-link-sep">/</span>');
}

function actionTemplate(action) {
  return `
    <article class="review-action-card">
      <h3>${action.title}</h3>
      <p>${action.description}</p>
    </article>
  `;
}

function siblingTemplate(item) {
  return `
    <article class="review-sibling-item ${item.is_current ? "current" : ""}">
      <div>
        <strong>${item.filename}</strong>
        <span>${item.modified_label}</span>
      </div>
      <span>${item.size_label}</span>
    </article>
  `;
}

function detailMetaTemplate(item) {
  return `
    <div class="review-detail-card">
      <span class="review-item-label">Reason</span>
      <strong>${item.reason}</strong>
      <p>${item.bucket}</p>
    </div>
    <div class="review-detail-card">
      <span class="review-item-label">Filename</span>
      <code>${item.filename}</code>
    </div>
    <div class="review-detail-card">
      <span class="review-item-label">Relative Path</span>
      <code>${item.relative_path}</code>
    </div>
    <div class="review-detail-card">
      <span class="review-item-label">Series / Season</span>
      <strong>${item.series_name}</strong>
      <p>${item.season_label}</p>
    </div>
  `;
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
  if (!reviewItemId || reviewItemLoading) {
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

    reviewItemTitle.textContent = payload.title || "Review Item";
    reviewItemSubtitle.textContent = item.filename;
    reviewItemBucket.textContent = item.bucket;
    reviewItemUpdated.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    reviewItemRefreshMs = (payload.refresh_interval_seconds || 15) * 1000;
    reviewItemRefresh.textContent = `${Math.round(reviewItemRefreshMs / 1000)}s`;
    reviewItemBreadcrumbs.innerHTML = breadcrumbTemplate(payload.breadcrumbs || []);
    reviewItemSummary.innerHTML = [
      { label: "Size", value: item.size_label, detail: item.extension },
      { label: "Series", value: item.series_name, detail: item.season_label },
      { label: "Folder Hint", value: item.folder_hint, detail: item.modified_label },
      { label: "Siblings", value: String((payload.siblings || []).length), detail: "same parent folder" },
    ]
      .map(metricTemplate)
      .join("");
    reviewItemMeta.innerHTML = detailMetaTemplate(item);
    reviewItemSiblings.innerHTML = (payload.siblings || []).length
      ? payload.siblings.map(siblingTemplate).join("")
      : `<div class="review-empty"><strong>No sibling files.</strong><span>当前目录下只有这一个媒体文件。</span></div>`;
    reviewItemActions.innerHTML = (payload.suggested_actions || []).map(actionTemplate).join("");
  } catch (error) {
    reviewItemMeta.innerHTML = `
      <div class="review-empty review-empty-error">
        <strong>Failed to load item detail.</strong>
        <span>${error.message || String(error)}</span>
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
      <strong>Missing review item id.</strong>
      <span>请从 Ops Review 列表页进入详情页。</span>
    </div>
  `;
} else {
  refreshReviewItem();
}
