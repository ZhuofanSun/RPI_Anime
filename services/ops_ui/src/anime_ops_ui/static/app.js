const servicesGrid = document.getElementById("services-grid");
const systemCards = document.getElementById("system-cards");
const queueCards = document.getElementById("queue-cards");
const networkCards = document.getElementById("network-cards");
const diagnostics = document.getElementById("diagnostics");
const pageTitle = document.getElementById("page-title");
const pageSubtitle = document.getElementById("page-subtitle");
const hostName = document.getElementById("host-name");
const lastUpdated = document.getElementById("last-updated");

function serviceInitials(name) {
  return name
    .split(/\s+/)
    .map((part) => part[0] || "")
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function statusClass(status) {
  const normalized = (status || "unknown").replace(/\s+/g, "").toLowerCase();
  if (["running", "healthy", "online"].includes(normalized)) return "status-running";
  if (["starting", "restarting"].includes(normalized)) return "status-starting";
  if (["offline", "exited", "dead"].includes(normalized)) return "status-offline";
  return "status-unknown";
}

function metricTemplate(card) {
  return `
    <article class="metric-card">
      <span class="metric-label">${card.label}</span>
      <span class="metric-value">${card.value}</span>
      <span class="metric-detail">${card.detail}</span>
    </article>
  `;
}

function serviceTemplate(service) {
  const href = service.href || "#";
  const disabled = service.href ? "" : "disabled";
  return `
    <article class="service-card">
      <div class="service-top">
        <div class="service-mark">${serviceInitials(service.name)}</div>
        <div class="status-dot ${statusClass(service.status)}" title="${service.status || "unknown"}"></div>
      </div>
      <div>
        <h3 class="service-name">${service.name}</h3>
        <p class="service-desc">${service.description}</p>
      </div>
      <div class="service-meta">${service.meta || "-"}</div>
      <div class="service-actions">
        <a class="service-link ${disabled}" href="${href}" ${service.href ? "" : 'aria-disabled="true"'}>
          ${service.href ? "Open Service" : "Coming Next"}
        </a>
      </div>
    </article>
  `;
}

function diagnosticsTemplate(items) {
  if (!items.length) {
    return `<div class="diagnostic-empty">All local data sources are responding.</div>`;
  }

  return items
    .map(
      (item) => `
      <article class="diagnostic-item">
        <span class="diagnostic-source">${item.source}</span>
        <p class="diagnostic-message">${item.message}</p>
      </article>
    `
    )
    .join("");
}

async function refreshOverview() {
  try {
    const response = await fetch("/api/overview", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    pageTitle.textContent = data.title;
    pageSubtitle.textContent = data.subtitle;
    hostName.textContent = data.host;
    lastUpdated.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    servicesGrid.innerHTML = data.services.map(serviceTemplate).join("");
    systemCards.innerHTML = data.system_cards.map(metricTemplate).join("");
    queueCards.innerHTML = data.queue_cards.map(metricTemplate).join("");
    networkCards.innerHTML = data.network_cards.map(metricTemplate).join("");
    diagnostics.innerHTML = diagnosticsTemplate(data.diagnostics || []);
  } catch (error) {
    diagnostics.innerHTML = diagnosticsTemplate([
      { source: "frontend", message: error.message || String(error) },
    ]);
  }
}

refreshOverview();
setInterval(refreshOverview, 8000);
