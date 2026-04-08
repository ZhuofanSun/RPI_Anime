const AnimeOpsCore = (() => {
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

  function readSessionCache(key) {
    try {
      const raw = window.sessionStorage.getItem(key);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object") return null;
      return parsed;
    } catch {
      return null;
    }
  }

  function writeSessionCache(key, payload) {
    try {
      window.sessionStorage.setItem(
        key,
        JSON.stringify({
          cachedAt: Date.now(),
          payload,
        })
      );
    } catch {}
  }

  async function fetchJson(url, options = {}) {
    const response = await fetch(url, options);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
  }

  function formatUpdatedLabel(cachedAt) {
    return new Date(cachedAt || Date.now()).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function flashTemplate(tone, title, message, extra = "") {
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
        ${extra}
      </div>
    `;
  }

  function setFlash(container, tone, title, message, extra = "") {
    if (!container) return;
    container.innerHTML = flashTemplate(tone, title, message, extra);
  }

  function clearFlash(container) {
    if (!container) return;
    container.innerHTML = "";
  }

  function renderEmptyState(title, detail, extraClass = "") {
    const classes = ["review-empty", extraClass].filter(Boolean).join(" ");
    return `
      <div class="${classes}">
        <strong>${escapeHtml(title)}</strong>
        <span>${escapeHtml(detail)}</span>
      </div>
    `;
  }

  function debounce(fn, delay = 220) {
    let timerId = null;
    return (...args) => {
      if (timerId) {
        window.clearTimeout(timerId);
      }
      timerId = window.setTimeout(() => {
        timerId = null;
        fn(...args);
      }, delay);
    };
  }

  function setQueryState(nextState, keys) {
    const url = new URL(window.location.href);
    keys.forEach((key) => {
      const value = nextState[key];
      if (value === undefined || value === null || value === "") {
        url.searchParams.delete(key);
      } else {
        url.searchParams.set(key, String(value));
      }
    });
    window.history.replaceState({}, "", url);
  }

  function getQueryState(keys) {
    const params = new URLSearchParams(window.location.search);
    return Object.fromEntries(keys.map((key) => [key, params.get(key) || ""]));
  }

  function formHasFocus(scope) {
    if (!scope) return false;
    const active = document.activeElement;
    return Boolean(active && scope.contains(active));
  }

  function createPageBootstrap({
    cacheKey = "",
    fetcher,
    render,
    onError,
    shouldPause,
    getIntervalMs,
    intervalMs = 8000,
  }) {
    let timerId = null;
    let inFlight = false;

    function currentIntervalMs() {
      const raw = typeof getIntervalMs === "function" ? Number(getIntervalMs()) : Number(intervalMs);
      return Number.isFinite(raw) && raw > 0 ? raw : 8000;
    }

    function schedule() {
      if (timerId) {
        window.clearTimeout(timerId);
      }
      timerId = window.setTimeout(() => {
        void tick();
      }, currentIntervalMs());
    }

    async function tick() {
      if (inFlight) return;
      if (typeof shouldPause === "function" && shouldPause()) {
        schedule();
        return;
      }

      inFlight = true;
      try {
        const payload = await fetcher();
        render(payload);
        if (cacheKey) {
          writeSessionCache(cacheKey, payload);
        }
      } catch (error) {
        onError?.(error);
      } finally {
        inFlight = false;
        schedule();
      }
    }

    function restore() {
      if (!cacheKey) return null;
      const cached = readSessionCache(cacheKey);
      if (!cached?.payload) return null;
      render(cached.payload, { cachedAt: cached.cachedAt });
      return cached;
    }

    function start() {
      restore();
      void tick();
      return api;
    }

    function stop() {
      if (timerId) {
        window.clearTimeout(timerId);
        timerId = null;
      }
    }

    const api = {
      currentIntervalMs,
      isBusy: () => inFlight,
      restore,
      schedule,
      start,
      stop,
      tick,
    };

    return api;
  }

  return {
    clearFlash,
    createPageBootstrap,
    debounce,
    escapeHtml,
    fetchJson,
    flashTemplate,
    formatUpdatedLabel,
    formHasFocus,
    getQueryState,
    metricTemplate,
    readSessionCache,
    renderEmptyState,
    setFlash,
    setQueryState,
    writeSessionCache,
  };
})();

window.AnimeOpsCore = AnimeOpsCore;
