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

function resolveExternalHref(href) {
  if (typeof href !== "string" || !href) {
    return href;
  }

  try {
    const currentUrl = new URL(window.location.href);
    const targetUrl = new URL(href, currentUrl);
    targetUrl.protocol = currentUrl.protocol;
    targetUrl.hostname = currentUrl.hostname;
    targetUrl.port = targetUrl.port || currentUrl.port;
    return targetUrl.toString();
  } catch {
    return href;
  }
}

function applyItem(link, item, navType, pageKey) {
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
    link.href = navType === "external" || item.target === "external" ? resolveExternalHref(item.href) : item.href;
  }

  if (navType === "external" || item.target === "external") {
    link.classList.add("is-external");
    link.target = "_blank";
    link.rel = "noopener noreferrer";
  } else {
    link.removeAttribute("target");
    link.removeAttribute("rel");
    const isActive = pageKey ? item.id === pageKey : link.classList.contains("is-active");
    link.classList.toggle("is-active", isActive);
  }

  applyTone(link, item.tone);
  applyBadge(link, item.badge);
}

function applyNavigationItems(navType, items, pageKey) {
  const group = document.querySelector(`[data-shell-nav="${navType}"]`);
  if (!group) return;

  const rowById = new Map();
  for (const row of group.querySelectorAll("[data-nav-item]")) {
    rowById.set(row.dataset.navItem, row);
  }

  for (const item of items) {
    const row = rowById.get(item.id);
    if (!row) continue;
    applyItem(row, item, navType, pageKey);
  }
}

function setupNavToggle() {
  const toggle = document.querySelector("[data-nav-toggle]");
  if (!toggle) return;
  const controlledId = toggle.getAttribute("aria-controls");
  if (!controlledId) return;
  const controlledRegion = document.getElementById(controlledId);
  if (!controlledRegion) return;

  const syncRegionState = () => {
    controlledRegion.hidden = toggle.getAttribute("aria-expanded") === "false";
  };
  syncRegionState();

  toggle.addEventListener("click", () => {
    const expanded = toggle.getAttribute("aria-expanded") !== "false";
    toggle.setAttribute("aria-expanded", expanded ? "false" : "true");
    syncRegionState();
  });
}

function setActionButtonBusy(button, busy, busyLabel = "Restarting…") {
  if (!button) return;
  if (busy) {
    if (button._originalMarkup === undefined) {
      button._originalMarkup = button.innerHTML;
    }
    button.disabled = true;
    button.textContent = busyLabel;
    return;
  }
  button.disabled = false;
  if (button._originalMarkup !== undefined) {
    button.innerHTML = button._originalMarkup;
    delete button._originalMarkup;
  }
}

let shellFeedbackTimerId = null;

function showShellFeedback(kind, message) {
  const flash = document.getElementById("shell-service-feedback");
  if (!flash) return;
  if (shellFeedbackTimerId) {
    window.clearTimeout(shellFeedbackTimerId);
  }
  flash.textContent = message;
  flash.className = `inline-feedback inline-feedback-${kind || "info"}`;
  shellFeedbackTimerId = window.setTimeout(() => {
    flash.className = "inline-feedback is-hidden";
    flash.textContent = "";
    shellFeedbackTimerId = null;
  }, 6000);
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  let payload = null;
  try {
    payload = await response.json();
  } catch {}
  if (!response.ok) {
    throw new Error(payload?.detail || payload?.message || `HTTP ${response.status}`);
  }
  return payload || {};
}

async function handleServiceAction(button) {
  const target = button.dataset.serviceAction;
  const name = button.dataset.serviceName || target || "service";
  const requiresReload = button.dataset.serviceReload === "true";
  const confirmMessage = requiresReload
    ? `将重启 ${name}，当前页面会短暂断开。继续吗？`
    : `将重启 ${name}。继续吗？`;
  if (!window.confirm(confirmMessage)) {
    return;
  }

  try {
    setActionButtonBusy(button, true);
    const payload = await postJson("/api/services/restart", { target });
    showShellFeedback("success", payload.message || `${name} 重启指令已发送。`);
    const reloadAfterSeconds = Number(payload.reload_after_seconds || 0);
    if (reloadAfterSeconds > 0 || requiresReload) {
      window.setTimeout(() => {
        window.location.reload();
      }, Math.max(reloadAfterSeconds, 5) * 1000);
      return;
    }
    window.setTimeout(() => {
      void hydrateShellNavigation();
    }, 1600);
  } catch (error) {
    showShellFeedback("error", error.message || `${name} 重启失败。`);
  } finally {
    setActionButtonBusy(button, false);
  }
}

async function handleStackAction(button) {
  const confirmMessage =
    "将依次重启 Jellyfin、qBittorrent、AutoBangumi、Glances、Postprocessor 和 Ops UI，不包含 Tailscale。继续吗？";
  if (!window.confirm(confirmMessage)) {
    return;
  }

  try {
    setActionButtonBusy(button, true);
    const payload = await postJson("/api/services/restart-all");
    showShellFeedback("warning", payload.message || "整套服务重启已安排。");
    const reloadAfterSeconds = Number(payload.reload_after_seconds || 8);
    window.setTimeout(() => {
      window.location.reload();
    }, Math.max(reloadAfterSeconds, 6) * 1000);
  } catch (error) {
    showShellFeedback("error", error.message || "整套服务重启失败。");
  } finally {
    setActionButtonBusy(button, false);
  }
}

function setupServiceActions() {
  const actionsRoot = document.querySelector("[data-shell-actions]");
  if (!actionsRoot) return;

  actionsRoot.addEventListener("click", (event) => {
    const serviceButton = event.target.closest("[data-service-action]");
    if (serviceButton) {
      event.preventDefault();
      void handleServiceAction(serviceButton);
      return;
    }

    const stackButton = event.target.closest("[data-stack-action]");
    if (stackButton) {
      event.preventDefault();
      void handleStackAction(stackButton);
    }
  });
}

async function hydrateShellNavigation() {
  const body = document.body;
  if (!body) return;
  const apiPath = body.dataset.navigationApiPath || "/api/navigation";
  const pageKey = body.dataset.page || "";

  try {
    const response = await fetch(apiPath, { cache: "no-store" });
    if (!response.ok) return;
    const payload = await response.json();
    if (!payload || typeof payload !== "object") return;
    const internalItems = Array.isArray(payload.internal) ? payload.internal : [];
    const externalItems = Array.isArray(payload.external) ? payload.external : [];
    applyNavigationItems("internal", internalItems, pageKey);
    applyNavigationItems("external", externalItems, pageKey);
  } catch {}
}

setupNavToggle();
setupServiceActions();
hydrateShellNavigation();
