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
let tailscaleCurrentControl = { action: "start", label: "开启 Tailscale" };

function statusClass(status) {
  const normalized = (status || "unknown").replace(/\s+/g, "").toLowerCase();
  if (["running", "healthy", "online"].includes(normalized)) return "status-running";
  if (["starting", "restarting"].includes(normalized)) return "status-starting";
  if (["offline", "exited", "dead"].includes(normalized)) return "status-offline";
  return "status-unknown";
}

function statusLabel(status) {
  const normalized = (status || "unknown").replace(/-/g, " ");
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
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
  const link = authUrl
    ? `<a class="flash-link" href="${escapeHtml(authUrl)}" target="_blank" rel="noreferrer">Open Login Link</a>`
    : "";
  return `
    <div class="flash-banner ${cls}">
      <strong>${escapeHtml(title)}</strong>
      <span>${escapeHtml(message)}</span>
      ${link}
    </div>
  `;
}

function peerTemplate(peer) {
  const tags = [
    `<span class="status-pill ${statusClass(peer.status)}"><span class="status-dot"></span><span>${escapeHtml(statusLabel(peer.status))}</span></span>`,
    peer.active ? `<span class="log-tag log-tag-source">active</span>` : "",
    peer.exit_node_option ? `<span class="log-tag log-tag-action">exit-node option</span>` : "",
    peer.exit_node ? `<span class="log-tag log-tag-level">exit-node</span>` : "",
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
          <span class="review-item-label">IPv6</span>
          <span class="review-item-value">${escapeHtml(peer.ipv6)}</span>
        </div>
        <div>
          <span class="review-item-label">Current Addr</span>
          <span class="review-item-value">${escapeHtml(peer.current_addr)}</span>
        </div>
        <div>
          <span class="review-item-label">Relay</span>
          <span class="review-item-value">${escapeHtml(peer.relay)}</span>
        </div>
        <div>
          <span class="review-item-label">Traffic</span>
          <span class="review-item-value">${escapeHtml(peer.rx_label)} ↓ / ${escapeHtml(peer.tx_label)} ↑</span>
        </div>
        <div>
          <span class="review-item-label">Last Write</span>
          <span class="review-item-value">${escapeHtml(peer.last_write_label)}</span>
        </div>
        <div>
          <span class="review-item-label">Last Handshake</span>
          <span class="review-item-value">${escapeHtml(peer.last_handshake_label)}</span>
        </div>
        <div>
          <span class="review-item-label">Last Seen</span>
          <span class="review-item-value">${escapeHtml(peer.last_seen_label)}</span>
        </div>
        <div>
          <span class="review-item-label">Key Expiry</span>
          <span class="review-item-value">${escapeHtml(peer.key_expiry_label)}</span>
        </div>
      </div>
    </article>
  `;
}

function diagnosticsTemplate(items) {
  if (!items.length) return "";
  return items
    .map((item) => flashTemplate(item.source || "tailscale", item.message || "Local API unavailable"))
    .join("");
}

function renderTailscale(payload, { cachedAt } = {}) {
  tailscaleTitle.textContent = payload.title || "Tailscale";
  tailscaleSubtitle.textContent = payload.subtitle || "";
  tailscaleSocket.textContent = payload.socket_path || "-";
  tailscaleUpdated.textContent = formatUpdatedLabel(cachedAt);
  tailscaleRefreshMs = (payload.refresh_interval_seconds || 15) * 1000;
  tailscaleRefresh.textContent = `${Math.round(tailscaleRefreshMs / 1000)}s`;
  tailscaleBackendBadge.textContent = `${payload.backend_state || "unknown"} · ${payload.reachability || "unknown"}`;
  tailscaleBackendBadge.className = `panel-badge ${payload.reachability === "Online" ? "" : "panel-badge-muted"}`;
  tailscaleSummary.innerHTML = (payload.summary_cards || []).map(metricTemplate).join("");
  tailscaleSelf.innerHTML = (payload.self_cards || []).map(metricTemplate).join("");
  tailscaleSelfNote.textContent = payload.self_note || "本机节点摘要会在这里显示。";
  tailscaleCurrentControl = payload.control || { action: "start", label: "开启 Tailscale" };
  tailscaleSelfBadge.textContent = `${payload.backend_state || "unknown"} · ${payload.reachability || "unknown"}`;
  tailscaleSelfBadge.className = `panel-badge ${payload.reachability === "Online" ? "" : "panel-badge-muted"}`;
  tailscaleToggleButton.textContent = tailscaleCurrentControl.label || "开启 Tailscale";
  tailscaleToggleButton.disabled = tailscaleActionInFlight;
  tailscaleToggleButton.className = `action-button action-button-compact ${
    tailscaleCurrentControl.action === "stop" ? "action-button-danger" : ""
  }`;
  tailscalePeerMeta.textContent = `在线 ${payload.peer_online || 0} / 共 ${payload.peer_total || 0} 台`;

  if (!payload.peers || !payload.peers.length) {
    tailscalePeerList.innerHTML = renderEmptyState("当前没有 peer。", "当其他设备加入 tailnet 后，这里会自动显示在线状态和尾网地址。");
  } else {
    tailscalePeerList.innerHTML = payload.peers.map(peerTemplate).join("");
  }

  tailscaleFlash.innerHTML = diagnosticsTemplate(payload.diagnostics || []);
}

function setActionBanner(tone, title, message, authUrl = "") {
  tailscaleActionStatus.innerHTML = actionBannerTemplate(tone, title, message, authUrl);
}

async function performTailscaleAction() {
  if (tailscaleActionInFlight) return;
  tailscaleActionInFlight = true;
  tailscaleToggleButton.disabled = true;
  setActionBanner("info", tailscaleCurrentControl.label || "Tailscale", "正在执行 Tailscale 控制动作。");
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
      tailscaleCurrentControl.label || "Tailscale",
      payload.message || "操作已完成。",
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
    tailscaleFlash.innerHTML = flashTemplate("Tailscale unavailable", error.message || String(error));
  },
});

tailscaleToggleButton?.addEventListener("click", performTailscaleAction);

tailscalePage.start();
