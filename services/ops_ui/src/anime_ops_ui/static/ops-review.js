const reviewTitle = document.getElementById("review-title");
const reviewSubtitle = document.getElementById("review-subtitle");
const reviewRoot = document.getElementById("review-root");
const reviewUpdated = document.getElementById("review-updated");
const reviewRefresh = document.getElementById("review-refresh");
const reviewSummary = document.getElementById("review-summary");
const reviewBucketFilter = document.getElementById("review-bucket-filter");
const reviewSearch = document.getElementById("review-search");
const reviewBucketChips = document.getElementById("review-bucket-chips");
const reviewList = document.getElementById("review-list");
const reviewListMeta = document.getElementById("review-list-meta");
const reviewFlash = document.getElementById("review-flash");
const REVIEW_CACHE_KEY = "anime-ops-ui-manual-review-cache-v1";
const REVIEW_FLASH_KEY = "anime-ops-ui-flash-v1";
const {
  createPageBootstrap,
  debounce,
  fetchJson,
  formatUpdatedLabel,
  getQueryState,
  metricTemplate,
  renderEmptyState,
  setQueryState,
} = window.AnimeOpsCore;

let reviewRefreshMs = 15000;
let reviewPayload = { buckets: [], items: [], summary_cards: [] };
const REVIEW_LIST_FALLBACKS = {
  en: {
    filter_all: "All Buckets",
    meta: "{visible} / {total} files",
    labels: {
      season: "Season",
      reason: "Reason",
      extension: "Extension",
      hint: "Hint",
      filename: "Filename",
      relative_path: "Relative Path",
    },
    actions: { view_detail: "View Detail" },
    flash: { default_title: "Action Complete" },
    empty: {
      filtered_title: "No files match the current filters.",
      filtered_detail: "Adjust the bucket or keyword to show files again.",
      idle_title: "No files need manual review right now.",
      idle_detail: "When the pipeline is healthy, unexpected files will appear here automatically.",
    },
    status: {
      load_failed_title: "Failed to load the manual review queue.",
      api_unavailable: "API unavailable",
    },
  },
};
const initialReviewState = getQueryState(["bucket", "q"]);
let reviewCurrentCopy = REVIEW_LIST_FALLBACKS.en;

function formatTemplate(template, values) {
  return Object.entries(values).reduce(
    (result, [key, value]) => result.replaceAll(`{${key}}`, String(value)),
    String(template || "")
  );
}

function reviewListCopy(payload) {
  const fallback = REVIEW_LIST_FALLBACKS.en;
  return {
    filter_all: payload.copy?.filter_all || fallback.filter_all,
    meta: payload.copy?.meta || fallback.meta,
    labels: {
      season: payload.copy?.labels?.season || fallback.labels.season,
      reason: payload.copy?.labels?.reason || fallback.labels.reason,
      extension: payload.copy?.labels?.extension || fallback.labels.extension,
      hint: payload.copy?.labels?.hint || fallback.labels.hint,
      filename: payload.copy?.labels?.filename || fallback.labels.filename,
      relative_path: payload.copy?.labels?.relative_path || fallback.labels.relative_path,
    },
    actions: {
      view_detail: payload.copy?.actions?.view_detail || fallback.actions.view_detail,
    },
    flash: {
      default_title: payload.copy?.flash?.default_title || fallback.flash.default_title,
    },
    empty: {
      filtered_title: payload.copy?.empty?.filtered_title || fallback.empty.filtered_title,
      filtered_detail: payload.copy?.empty?.filtered_detail || fallback.empty.filtered_detail,
      idle_title: payload.copy?.empty?.idle_title || fallback.empty.idle_title,
      idle_detail: payload.copy?.empty?.idle_detail || fallback.empty.idle_detail,
    },
    status: {
      load_failed_title: payload.copy?.status?.load_failed_title || fallback.status.load_failed_title,
      api_unavailable: payload.copy?.status?.api_unavailable || fallback.status.api_unavailable,
    },
  };
}

function bucketOptionsTemplate(buckets, copy) {
  return [
    `<option value="">${copy.filter_all}</option>`,
    ...buckets.map((bucket) => `<option value="${bucket.bucket}">${bucket.label} · ${bucket.count}</option>`),
  ].join("");
}

function bucketChipsTemplate(buckets, activeBucket) {
  return buckets
    .map((bucket) => {
      const active = activeBucket === bucket.bucket ? "active" : "";
      return `
        <button class="review-chip ${active}" type="button" data-review-bucket="${bucket.bucket}">
          <span>${bucket.label}</span>
          <strong>${bucket.count}</strong>
        </button>
      `;
    })
    .join("");
}

function reviewItemTemplate(item, copy) {
  return `
    <article class="review-item">
      <div class="review-item-top">
        <div class="review-item-heading">
          <span class="review-item-bucket">${item.bucket_label || item.bucket}</span>
          <h3>${item.series_name}</h3>
        </div>
        <div class="review-item-side">
          <span class="review-item-size">${item.size_label}</span>
          <span class="review-item-modified">${item.modified_label}</span>
        </div>
      </div>
      <div class="review-item-grid">
        <div>
          <span class="review-item-label">${copy.labels.season}</span>
          <span class="review-item-value">${item.season_label}</span>
        </div>
        <div>
          <span class="review-item-label">${copy.labels.reason}</span>
          <span class="review-item-value">${item.reason}</span>
        </div>
        <div>
          <span class="review-item-label">${copy.labels.extension}</span>
          <span class="review-item-value">${item.extension}</span>
        </div>
        <div>
          <span class="review-item-label">${copy.labels.hint}</span>
          <span class="review-item-value">${item.folder_hint}</span>
        </div>
      </div>
      <div class="review-item-paths">
        <div>
          <span class="review-item-label">${copy.labels.filename}</span>
          <code>${item.filename}</code>
        </div>
        <div>
          <span class="review-item-label">${copy.labels.relative_path}</span>
          <code>${item.relative_path}</code>
        </div>
      </div>
      <div class="review-item-actions">
        <a class="ghost-link" href="/ops-review/item?id=${encodeURIComponent(item.id)}">${copy.actions.view_detail}</a>
      </div>
    </article>
  `;
}

function consumeFlash() {
  try {
    const raw = window.sessionStorage.getItem(REVIEW_FLASH_KEY);
    if (!raw) return null;
    window.sessionStorage.removeItem(REVIEW_FLASH_KEY);
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    return parsed;
  } catch {
    return null;
  }
}

function flashTemplate(flash) {
  const tone = flash.tone === "error" ? "flash-error" : "flash-success";
  return `
    <div class="flash-banner ${tone}">
      <strong>${flash.title || reviewCurrentCopy.flash.default_title}</strong>
      <span>${flash.message || ""}</span>
    </div>
  `;
}

function applyFilters() {
  const copy = reviewListCopy(reviewPayload);
  const activeBucket = reviewBucketFilter.value;
  const keyword = (reviewSearch.value || "").trim().toLowerCase();
  const filteredItems = (reviewPayload.items || []).filter((item) => {
    const bucketMatch = !activeBucket || item.bucket === activeBucket;
    if (!bucketMatch) return false;
    if (!keyword) return true;
    return [item.series_name, item.filename, item.relative_path, item.reason]
      .join(" ")
      .toLowerCase()
      .includes(keyword);
  });

  reviewListMeta.textContent = formatTemplate(copy.meta, {
    visible: filteredItems.length,
    total: (reviewPayload.items || []).length,
  });

  if (!filteredItems.length) {
    const emptyTitle = (reviewPayload.items || []).length
      ? copy.empty.filtered_title
      : copy.empty.idle_title;
    const emptyDetail = (reviewPayload.items || []).length
      ? copy.empty.filtered_detail
      : copy.empty.idle_detail;
    reviewList.innerHTML = renderEmptyState(emptyTitle, emptyDetail);
  } else {
    reviewList.innerHTML = filteredItems.map((item) => reviewItemTemplate(item, copy)).join("");
  }

  reviewBucketChips.innerHTML = bucketChipsTemplate(reviewPayload.buckets || [], activeBucket);
  reviewBucketChips.querySelectorAll("[data-review-bucket]").forEach((button) => {
    button.addEventListener("click", () => {
      reviewBucketFilter.value = button.dataset.reviewBucket || "";
      applyFilters();
    });
  });

  setQueryState(
    {
      bucket: activeBucket,
      q: reviewSearch.value.trim(),
    },
    ["bucket", "q"]
  );
}

function renderReview(payload, { cachedAt } = {}) {
  reviewCurrentCopy = reviewListCopy(payload);
  const currentBucket = reviewBucketFilter.value || initialReviewState.bucket;
  reviewPayload = payload;
  reviewTitle.textContent = payload.title || "Ops Review";
  reviewSubtitle.textContent = payload.subtitle || "";
  reviewRoot.textContent = payload.root || "-";
  reviewUpdated.textContent = formatUpdatedLabel(cachedAt);
  reviewRefreshMs = (payload.refresh_interval_seconds || 15) * 1000;
  reviewRefresh.textContent = `${Math.round(reviewRefreshMs / 1000)}s`;
  reviewSummary.innerHTML = (payload.summary_cards || []).map(metricTemplate).join("");
  reviewBucketFilter.innerHTML = bucketOptionsTemplate(payload.buckets || [], reviewCurrentCopy);
  if (currentBucket && Array.from(reviewBucketFilter.options).some((option) => option.value === currentBucket)) {
    reviewBucketFilter.value = currentBucket;
  }
  applyFilters();
}

const reviewPage = createPageBootstrap({
  cacheKey: REVIEW_CACHE_KEY,
  fetcher: () => fetchJson("/api/manual-review", { cache: "no-store" }),
  render: renderReview,
  getIntervalMs: () => reviewRefreshMs,
  onError: (error) => {
    reviewList.innerHTML = renderEmptyState(
      reviewCurrentCopy.status.load_failed_title,
      error.message || String(error),
      "review-empty-error"
    );
    reviewListMeta.textContent = reviewCurrentCopy.status.api_unavailable;
  },
});

const debouncedApplyFilters = debounce(applyFilters, 180);

reviewBucketFilter.addEventListener("change", applyFilters);
reviewSearch.addEventListener("input", debouncedApplyFilters);

if (initialReviewState.bucket) reviewBucketFilter.value = initialReviewState.bucket;
if (initialReviewState.q) reviewSearch.value = initialReviewState.q;

const flash = consumeFlash();
if (flash && reviewFlash) {
  reviewFlash.innerHTML = flashTemplate(flash);
}

reviewPage.start();
