const tailscaleTitle = document.getElementById("tailscale-title");
const tailscaleSubtitle = document.getElementById("tailscale-subtitle");
const tailscaleSocket = document.getElementById("tailscale-socket");
const tailscaleUpdated = document.getElementById("tailscale-updated");
const tailscaleRefresh = document.getElementById("tailscale-refresh");
const tailscaleBackendBadge = document.getElementById("tailscale-backend-badge");
const tailscaleSummary = document.getElementById("tailscale-summary");
const tailscaleSelf = document.getElementById("tailscale-self");
const tailscaleSelfBadge = document.getElementById("tailscale-self-badge");
const tailscaleSelfNote = document.getElementById("tailscale-self-note");
const tailscaleToggleButton = document.getElementById("tailscale-toggle-button");
const tailscaleActionStatus = document.getElementById("tailscale-action-status");
const tailscalePeerMeta = document.getElementById("tailscale-peer-meta");
const tailscalePeerList = document.getElementById("tailscale-peer-list");
const tailscaleFlash = document.getElementById("tailscale-flash");
const TAILSCALE_CACHE_KEY = "anime-ops-ui-tailscale-cache-v1";
const {
  createPageBootstrap,
  escapeHtml,
  fetchJson,
  formatUpdatedLabel,
  metricTemplate,
  renderEmptyState,
} = window.AnimeOpsCore;

let tailscaleRefreshMs = 15000;
let tailscaleActionInFlight = false;
let tailscaleCurrentControl = { action: "start", label: "Start Tailscale" };
let tailscalePayload = {};
const TAILSCALE_FALLBACK_COPY = {
  meta: {
    refresh_suffix: "s",
    peer_meta: "{online} online / {total} total",
  },
  defaults: {
    control_label: "Start Tailscale",
    self_note: "Node summary will appear here.",
  },
  link_label: "Open Sign-In",
  peer_tags: {
    active: "active",
    exit_node_option: "exit-node option",
    exit_node: "exit-node",
  },
  peer_fields: {
    ipv6: "IPv6",
    current_addr: "Current Addr",
    relay: "Relay",
    traffic: "Traffic",
    last_write: "Last Write",
    last_handshake: "Last Handshake",
    last_seen: "Last Seen",
    key_expiry: "Key Expiry",
  },
  peer_status: {
    online: "Online",
    offline: "Offline",
    unknown: "Unknown",
  },
  empty: {
    title: "No peers right now.",
    detail: "When other devices join the tailnet, this list will populate automatically.",
  },
  action: {
    in_progress: "Running the Tailscale control action.",
    success_fallback: "Action complete.",
  },
  diagnostics: {
    source_fallback: "tailscale",
    message_fallback: "Local API unavailable",
    unavailable_title: "Tailscale unavailable",
  },
};

function formatTemplate(template, values) {
  return Object.entries(values).reduce(
    (result, [key, value]) => result.replaceAll(`{${key}}`, String(value)),
    String(template || "")
  );
}

function tailscaleCopy(payload) {
  return {
    meta: {
      refresh_suffix: payload.copy?.meta?.refresh_suffix || TAILSCALE_FALLBACK_COPY.meta.refresh_suffix,
      peer_meta: payload.copy?.meta?.peer_meta || TAILSCALE_FALLBACK_COPY.meta.peer_meta,
    },
    defaults: {
      control_label:
        payload.copy?.defaults?.control_label || TAILSCALE_FALLBACK_COPY.defaults.control_label,
      self_note: payload.copy?.defaults?.self_note || TAILSCALE_FALLBACK_COPY.defaults.self_note,
    },
    link_label: payload.copy?.link_label || TAILSCALE_FALLBACK_COPY.link_label,
    peer_tags: {
      active: payload.copy?.peer_tags?.active || TAILSCALE_FALLBACK_COPY.peer_tags.active,
      exit_node_option:
        payload.copy?.peer_tags?.exit_node_option || TAILSCALE_FALLBACK_COPY.peer_tags.exit_node_option,
      exit_node: payload.copy?.peer_tags?.exit_node || TAILSCALE_FALLBACK_COPY.peer_tags.exit_node,
    },
    peer_fields: {
      ipv6: payload.copy?.peer_fields?.ipv6 || TAILSCALE_FALLBACK_COPY.peer_fields.ipv6,
      current_addr:
        payload.copy?.peer_fields?.current_addr || TAILSCALE_FALLBACK_COPY.peer_fields.current_addr,
      relay: payload.copy?.peer_fields?.relay || TAILSCALE_FALLBACK_COPY.peer_fields.relay,
      traffic: payload.copy?.peer_fields?.traffic || TAILSCALE_FALLBACK_COPY.peer_fields.traffic,
      last_write:
        payload.copy?.peer_fields?.last_write || TAILSCALE_FALLBACK_COPY.peer_fields.last_write,
      last_handshake:
        payload.copy?.peer_fields?.last_handshake || TAILSCALE_FALLBACK_COPY.peer_fields.last_handshake,
      last_seen:
        payload.copy?.peer_fields?.last_seen || TAILSCALE_FALLBACK_COPY.peer_fields.last_seen,
      key_expiry:
        payload.copy?.peer_fields?.key_expiry || TAILSCALE_FALLBACK_COPY.peer_fields.key_expiry,
    },
    peer_status: {
      online: payload.copy?.peer_status?.online || TAILSCALE_FALLBACK_COPY.peer_status.online,
      offline: payload.copy?.peer_status?.offline || TAILSCALE_FALLBACK_COPY.peer_status.offline,
      unknown: payload.copy?.peer_status?.unknown || TAILSCALE_FALLBACK_COPY.peer_status.unknown,
    },
    empty: {
      title: payload.copy?.empty?.title || TAILSCALE_FALLBACK_COPY.empty.title,
      detail: payload.copy?.empty?.detail || TAILSCALE_FALLBACK_COPY.empty.detail,
    },
    action: {
      in_progress:
        payload.copy?.action?.in_progress || TAILSCALE_FALLBACK_COPY.action.in_progress,
      success_fallback:
        payload.copy?.action?.success_fallback || TAILSCALE_FALLBACK_COPY.action.success_fallback,
    },
    diagnostics: {
      source_fallback:
        payload.copy?.diagnostics?.source_fallback || TAILSCALE_FALLBACK_COPY.diagnostics.source_fallback,
      message_fallback:
        payload.copy?.diagnostics?.message_fallback || TAILSCALE_FALLBACK_COPY.diagnostics.message_fallback,
      unavailable_title:
        payload.copy?.diagnostics?.unavailable_title ||
        TAILSCALE_FALLBACK_COPY.diagnostics.unavailable_title,
    },
  };
}

function statusClass(status) {
  const normalized = (status || "unknown").replace(/\s+/g, "").toLowerCase();
  if (["running", "healthy", "online"].includes(normalized)) return "status-running";
  if (["starting", "restarting"].includes(normalized)) return "status-starting";
  if (["offline", "exited", "dead"].includes(normalized)) return "status-offline";
  return "status-unknown";
}

function statusLabel(status, copy) {
  const normalized = String(status || "unknown").replace(/\s+/g, "").toLowerCase();
  if (normalized === "online") return copy.peer_status.online;
  if (normalized === "offline") return copy.peer_status.offline;
  return copy.peer_status.unknown;
}

function flashTemplate(title, message) {
  return `
    <div class="flash-banner flash-error">
      <strong>${escapeHtml(title)}</strong>
      <span>${escapeHtml(message)}</span>
    </div>
  `;
}

function actionBannerTemplate(tone, title, message, authUrl) {
  const cls = tone === "error" ? "flash-error" : tone === "success" ? "flash-success" : "flash-info";
  const copy = tailscaleCopy(tailscalePayload);
  const link = authUrl
    ? `<a class="flash-link" href="${escapeHtml(authUrl)}" target="_blank" rel="noreferrer">${escapeHtml(copy.link_label)}</a>`
    : "";
  return `
    <div class="flash-banner ${cls}">
      <strong>${escapeHtml(title)}</strong>
      <span>${escapeHtml(message)}</span>
      ${link}
    </div>
  `;
}

function peerTemplate(peer, copy) {
  const tags = [
    `<span class="status-pill ${statusClass(peer.status)}"><span class="status-dot"></span><span>${escapeHtml(statusLabel(peer.status, copy))}</span></span>`,
    peer.active ? `<span class="log-tag log-tag-source">${escapeHtml(copy.peer_tags.active)}</span>` : "",
    peer.exit_node_option ? `<span class="log-tag log-tag-action">${escapeHtml(copy.peer_tags.exit_node_option)}</span>` : "",
    peer.exit_node ? `<span class="log-tag log-tag-level">${escapeHtml(copy.peer_tags.exit_node)}</span>` : "",
  ]
    .filter(Boolean)
    .join("");

  return `
    <article class="review-item">
      <div class="review-item-top">
        <div class="review-item-heading">
          <div class="tailscale-peer-topline">${tags}</div>
          <h3>${escapeHtml(peer.host_name)}</h3>
          <span class="service-meta">${escapeHtml(peer.dns_name)}</span>
        </div>
        <div class="review-item-side">
          <span class="review-item-size">${escapeHtml(peer.ip)}</span>
          <span>${escapeHtml(peer.os)}</span>
        </div>
      </div>
      <div class="review-item-grid">
        <div>
          <span class="review-item-label">${copy.peer_fields.ipv6}</span>
          <span class="review-item-value">${escapeHtml(peer.ipv6)}</span>
        </div>
        <div>
          <span class="review-item-label">${copy.peer_fields.current_addr}</span>
          <span class="review-item-value">${escapeHtml(peer.current_addr)}</span>
        </div>
        <div>
          <span class="review-item-label">${copy.peer_fields.relay}</span>
          <span class="review-item-value">${escapeHtml(peer.relay)}</span>
        </div>
        <div>
          <span class="review-item-label">${copy.peer_fields.traffic}</span>
          <span class="review-item-value">${escapeHtml(peer.rx_label)} ↓ / ${escapeHtml(peer.tx_label)} ↑</span>
        </div>
        <div>
          <span class="review-item-label">${copy.peer_fields.last_write}</span>
          <span class="review-item-value">${escapeHtml(peer.last_write_label)}</span>
        </div>
        <div>
          <span class="review-item-label">${copy.peer_fields.last_handshake}</span>
          <span class="review-item-value">${escapeHtml(peer.last_handshake_label)}</span>
        </div>
        <div>
          <span class="review-item-label">${copy.peer_fields.last_seen}</span>
          <span class="review-item-value">${escapeHtml(peer.last_seen_label)}</span>
        </div>
        <div>
          <span class="review-item-label">${copy.peer_fields.key_expiry}</span>
          <span class="review-item-value">${escapeHtml(peer.key_expiry_label)}</span>
        </div>
      </div>
    </article>
  `;
}

function diagnosticsTemplate(items, copy) {
  if (!items.length) return "";
  return items
    .map((item) => flashTemplate(item.source || copy.diagnostics.source_fallback, item.message || copy.diagnostics.message_fallback))
    .join("");
}

function renderTailscale(payload, { cachedAt } = {}) {
  const copy = tailscaleCopy(payload);
  tailscalePayload = payload;
  tailscaleTitle.textContent = payload.title || "Tailscale";
  tailscaleSubtitle.textContent = payload.subtitle || "";
  tailscaleSocket.textContent = payload.socket_path || "-";
  tailscaleUpdated.textContent = formatUpdatedLabel(cachedAt);
  tailscaleRefreshMs = (payload.refresh_interval_seconds || 15) * 1000;
  tailscaleRefresh.textContent = `${Math.round(tailscaleRefreshMs / 1000)}${copy.meta.refresh_suffix}`;
  tailscaleBackendBadge.textContent = `${payload.backend_state || "unknown"} · ${payload.reachability || "unknown"}`;
  tailscaleBackendBadge.className = `panel-badge ${payload.status?.reachable ? "" : "panel-badge-muted"}`;
  tailscaleSummary.innerHTML = (payload.summary_cards || []).map(metricTemplate).join("");
  tailscaleSelf.innerHTML = (payload.self_cards || []).map(metricTemplate).join("");
  tailscaleSelfNote.textContent = payload.self_note || copy.defaults.self_note;
  tailscaleCurrentControl = payload.control || { action: "start", label: copy.defaults.control_label };
  tailscaleSelfBadge.textContent = `${payload.backend_state || "unknown"} · ${payload.reachability || "unknown"}`;
  tailscaleSelfBadge.className = `panel-badge ${payload.status?.reachable ? "" : "panel-badge-muted"}`;
  tailscaleToggleButton.textContent = tailscaleCurrentControl.label || copy.defaults.control_label;
  tailscaleToggleButton.disabled = tailscaleActionInFlight;
  tailscaleToggleButton.className = `action-button action-button-compact ${
    tailscaleCurrentControl.action === "stop" ? "action-button-danger" : ""
  }`;
  tailscalePeerMeta.textContent = formatTemplate(copy.meta.peer_meta, {
    online: payload.peer_online || 0,
    total: payload.peer_total || 0,
  });

  if (!payload.peers || !payload.peers.length) {
    tailscalePeerList.innerHTML = renderEmptyState(copy.empty.title, copy.empty.detail);
  } else {
    tailscalePeerList.innerHTML = payload.peers.map((peer) => peerTemplate(peer, copy)).join("");
  }

  tailscaleFlash.innerHTML = diagnosticsTemplate(payload.diagnostics || [], copy);
}

function setActionBanner(tone, title, message, authUrl = "") {
  tailscaleActionStatus.innerHTML = actionBannerTemplate(tone, title, message, authUrl);
}

async function performTailscaleAction() {
  if (tailscaleActionInFlight) return;
  tailscaleActionInFlight = true;
  tailscaleToggleButton.disabled = true;
  setActionBanner(
    "info",
    tailscaleCurrentControl.label || tailscaleCopy(tailscalePayload).defaults.control_label,
    tailscaleCopy(tailscalePayload).action.in_progress
  );
  try {
    const response = await fetch("/api/tailscale/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: tailscaleCurrentControl.action || "start" }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || payload.message || `HTTP ${response.status}`);
    }
    setActionBanner(
      payload.auth_url ? "info" : "success",
      tailscaleCurrentControl.label || tailscaleCopy(tailscalePayload).defaults.control_label,
      payload.message || tailscaleCopy(tailscalePayload).action.success_fallback,
      payload.auth_url || ""
    );
    await tailscalePage.tick();
  } catch (error) {
    setActionBanner("error", tailscaleCurrentControl.label || "Tailscale", error.message || String(error));
  } finally {
    tailscaleActionInFlight = false;
    tailscaleToggleButton.disabled = false;
  }
}

const tailscalePage = createPageBootstrap({
  cacheKey: TAILSCALE_CACHE_KEY,
  fetcher: () => fetchJson("/api/tailscale", { cache: "no-store" }),
  render: renderTailscale,
  getIntervalMs: () => tailscaleRefreshMs,
  onError: (error) => {
    tailscaleFlash.innerHTML = flashTemplate(
      tailscaleCopy(tailscalePayload).diagnostics.unavailable_title,
      error.message || String(error)
    );
  },
});

tailscaleToggleButton?.addEventListener("click", performTailscaleAction);

tailscalePage.start();
