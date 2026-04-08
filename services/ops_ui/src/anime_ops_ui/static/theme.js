const THEME_STORAGE_KEY = "anime-ops-ui-theme";

function themeCopy() {
  return (((typeof window !== "undefined" && window.__OPS_UI_COPY__) || {}).theme || {});
}

function setButtonState(button, active, label) {
  if (!button) return;
  if (typeof button.setAttribute === "function") {
    button.setAttribute("aria-pressed", active ? "true" : "false");
    if (label) {
      button.setAttribute("aria-label", `${themeCopy().label || "Theme"}: ${label}`);
    }
  }
  if (button.classList && typeof button.classList.toggle === "function") {
    button.classList.toggle("is-active", active);
  }
}

function getPreferredTheme() {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "light" || stored === "dark") {
      return stored;
    }
  } catch {
    // Fall back to system preference when storage is unavailable.
  }
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function applyTheme(theme, { persist = true } = {}) {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
  if (persist) {
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // Ignore storage write failures and still update the live document state.
    }
  }

  const copy = themeCopy();
  document.querySelectorAll("[data-theme-option]").forEach((button) => {
    const option = button.dataset.themeOption;
    const isActive = option === theme;
    const label = option === "dark" ? copy.dark || "Dark" : copy.light || "Light";
    setButtonState(button, isActive, label);
  });
}

applyTheme(getPreferredTheme(), { persist: false });

document.addEventListener("DOMContentLoaded", () => {
  applyTheme(getPreferredTheme(), { persist: false });

  document.querySelectorAll("[data-theme-option]").forEach((button) => {
    button.addEventListener("click", () => {
      const nextTheme = button.dataset.themeOption;
      if (nextTheme === "light" || nextTheme === "dark") {
        applyTheme(nextTheme);
      }
    });
  });
});
