function clearToneClasses(link) {
  const stale = [];
  for (const className of link.classList) {
    if (className.startsWith("is-tone-")) {
      stale.push(className);
    }
  }
  stale.forEach((className) => link.classList.remove(className));
}

function applyTone(link, tone) {
  clearToneClasses(link);
  const normalizedTone = tone || "neutral";
  link.dataset.navTone = normalizedTone;
  link.classList.add(`is-tone-${normalizedTone}`);
}

function applyBadge(link, badge) {
  const badgeNode = link.querySelector("[data-nav-badge]");
  if (!badgeNode) return;
  if (badge === null || badge === undefined || badge === "") {
    badgeNode.textContent = "";
    badgeNode.hidden = true;
    return;
  }
  badgeNode.textContent = String(badge);
  badgeNode.hidden = false;
}

function applyItem(link, item, navType) {
  if (!item || typeof item !== "object") return;

  if (typeof item.label === "string") {
    const labelNode = link.querySelector("[data-nav-label]");
    if (labelNode) labelNode.textContent = item.label;
  }
  if (typeof item.icon === "string") {
    const iconNode = link.querySelector("[data-nav-icon]");
    if (iconNode) iconNode.textContent = item.icon;
  }
  if (typeof item.href === "string" && item.href) {
    link.href = item.href;
  }

  if (navType === "external" || item.target === "external") {
    link.classList.add("is-external");
    link.target = "_blank";
    link.rel = "noopener noreferrer";
  } else {
    link.removeAttribute("target");
    link.removeAttribute("rel");
    link.classList.toggle("is-active", window.location.pathname === item.path || window.location.pathname === item.href);
  }

  applyTone(link, item.tone);
  applyBadge(link, item.badge);
}

function applyNavigationItems(navType, items) {
  const group = document.querySelector(`[data-shell-nav="${navType}"]`);
  if (!group) return;

  const rowById = new Map();
  for (const row of group.querySelectorAll("[data-nav-item]")) {
    rowById.set(row.dataset.navItem, row);
  }

  for (const item of items) {
    const row = rowById.get(item.id);
    if (!row) continue;
    applyItem(row, item, navType);
  }
}

function setupNavToggle() {
  const toggle = document.querySelector("[data-nav-toggle]");
  if (!toggle) return;

  toggle.addEventListener("click", () => {
    const collapsed = document.body.dataset.navCollapsed === "true";
    const next = !collapsed;
    document.body.dataset.navCollapsed = next ? "true" : "false";
    toggle.setAttribute("aria-expanded", next ? "false" : "true");
  });
}

async function hydrateShellNavigation() {
  const body = document.body;
  if (!body) return;
  const apiPath = body.dataset.navigationApiPath || "/api/navigation";

  try {
    const response = await fetch(apiPath, { cache: "no-store" });
    if (!response.ok) return;
    const payload = await response.json();
    if (!payload || typeof payload !== "object") return;
    const internalItems = Array.isArray(payload.internal) ? payload.internal : [];
    const externalItems = Array.isArray(payload.external) ? payload.external : [];
    applyNavigationItems("internal", internalItems);
    applyNavigationItems("external", externalItems);
  } catch {}
}

setupNavToggle();
hydrateShellNavigation();
