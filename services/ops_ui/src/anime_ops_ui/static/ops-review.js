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

let reviewRefreshMs = 15000;
let reviewTimerId = null;
let reviewFetchInFlight = false;
let reviewPayload = { buckets: [], items: [], summary_cards: [] };

function metricTemplate(card) {
  return `
    <article class="metric-card">
      <span class="metric-label">${card.label}</span>
      <span class="metric-value">${card.value}</span>
      <span class="metric-detail">${card.detail}</span>
    </article>
  `;
}

function bucketOptionsTemplate(buckets) {
  return [
    `<option value="">All buckets</option>`,
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

function reviewItemTemplate(item) {
  return `
    <article class="review-item">
      <div class="review-item-top">
        <div class="review-item-heading">
          <span class="review-item-bucket">${item.bucket}</span>
          <h3>${item.series_name}</h3>
        </div>
        <div class="review-item-side">
          <span class="review-item-size">${item.size_label}</span>
          <span class="review-item-modified">${item.modified_label}</span>
        </div>
      </div>
      <div class="review-item-grid">
        <div>
          <span class="review-item-label">Season</span>
          <span class="review-item-value">${item.season_label}</span>
        </div>
        <div>
          <span class="review-item-label">Reason</span>
          <span class="review-item-value">${item.reason}</span>
        </div>
        <div>
          <span class="review-item-label">Extension</span>
          <span class="review-item-value">${item.extension}</span>
        </div>
        <div>
          <span class="review-item-label">Hint</span>
          <span class="review-item-value">${item.folder_hint}</span>
        </div>
      </div>
      <div class="review-item-paths">
        <div>
          <span class="review-item-label">Filename</span>
          <code>${item.filename}</code>
        </div>
        <div>
          <span class="review-item-label">Relative Path</span>
          <code>${item.relative_path}</code>
        </div>
      </div>
      <div class="review-item-actions">
        <a class="ghost-link" href="/ops-review/item?id=${encodeURIComponent(item.id)}">查看详情</a>
      </div>
    </article>
  `;
}

function loadReviewCache() {
  try {
    const raw = window.sessionStorage.getItem(REVIEW_CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || !parsed.payload) return null;
    return parsed;
  } catch {
    return null;
  }
}

function saveReviewCache(payload) {
  try {
    window.sessionStorage.setItem(
      REVIEW_CACHE_KEY,
      JSON.stringify({
        cachedAt: Date.now(),
        payload,
      })
    );
  } catch {}
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
      <strong>${flash.title || "Action completed"}</strong>
      <span>${flash.message || ""}</span>
    </div>
  `;
}

function applyFilters() {
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

  reviewListMeta.textContent = `${filteredItems.length} / ${(reviewPayload.items || []).length} files`;

  if (!filteredItems.length) {
    const emptyTitle = (reviewPayload.items || []).length
      ? "当前筛选条件下没有匹配文件。"
      : "当前没有待处理文件。";
    const emptyDetail = (reviewPayload.items || []).length
      ? "调整 bucket 或关键字后会重新显示列表。"
      : "下载链路运行正常时，这里会在出现异常文件后自动补进队列。";
    reviewList.innerHTML = `
      <div class="review-empty">
        <strong>${emptyTitle}</strong>
        <span>${emptyDetail}</span>
      </div>
    `;
  } else {
    reviewList.innerHTML = filteredItems.map(reviewItemTemplate).join("");
  }

  reviewBucketChips.innerHTML = bucketChipsTemplate(reviewPayload.buckets || [], activeBucket);
  reviewBucketChips.querySelectorAll("[data-review-bucket]").forEach((button) => {
    button.addEventListener("click", () => {
      reviewBucketFilter.value = button.dataset.reviewBucket || "";
      applyFilters();
    });
  });
}

function renderReview(payload, { cachedAt } = {}) {
  const currentBucket = reviewBucketFilter.value;
  reviewPayload = payload;
  reviewTitle.textContent = payload.title || "Ops Review";
  reviewSubtitle.textContent = payload.subtitle || "";
  reviewRoot.textContent = payload.root || "-";
  reviewUpdated.textContent = new Date(cachedAt || Date.now()).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
  reviewRefreshMs = (payload.refresh_interval_seconds || 15) * 1000;
  reviewRefresh.textContent = `${Math.round(reviewRefreshMs / 1000)}s`;
  reviewSummary.innerHTML = (payload.summary_cards || []).map(metricTemplate).join("");
  reviewBucketFilter.innerHTML = bucketOptionsTemplate(payload.buckets || []);
  if (currentBucket && Array.from(reviewBucketFilter.options).some((option) => option.value === currentBucket)) {
    reviewBucketFilter.value = currentBucket;
  }
  applyFilters();
}

function scheduleReviewRefresh() {
  if (reviewTimerId) {
    clearTimeout(reviewTimerId);
  }
  reviewTimerId = window.setTimeout(() => {
    refreshReview();
  }, reviewRefreshMs);
}

async function refreshReview() {
  if (reviewFetchInFlight) {
    return;
  }
  reviewFetchInFlight = true;
  try {
    const response = await fetch("/api/manual-review", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    renderReview(payload);
    saveReviewCache(payload);
  } catch (error) {
    reviewList.innerHTML = `
      <div class="review-empty review-empty-error">
        <strong>Failed to load manual review queue.</strong>
        <span>${error.message || String(error)}</span>
      </div>
    `;
    reviewListMeta.textContent = "API unavailable";
  } finally {
    reviewFetchInFlight = false;
    scheduleReviewRefresh();
  }
}

reviewBucketFilter.addEventListener("change", applyFilters);
reviewSearch.addEventListener("input", applyFilters);

const cachedReview = loadReviewCache();
if (cachedReview) {
  renderReview(cachedReview.payload, { cachedAt: cachedReview.cachedAt });
}

const flash = consumeFlash();
if (flash && reviewFlash) {
  reviewFlash.innerHTML = flashTemplate(flash);
}

refreshReview();
