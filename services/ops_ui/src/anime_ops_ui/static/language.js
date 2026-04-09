function setLanguageButtonState(button, active) {
  if (!button) return;
  if (typeof button.setAttribute === "function") {
    button.setAttribute("aria-pressed", active ? "true" : "false");
  }
  if (button.classList && typeof button.classList.toggle === "function") {
    button.classList.toggle("is-active", active);
  }
}

function syncLanguageButtons(currentLocale) {
  document.querySelectorAll("[data-language-option]").forEach((button) => {
    setLanguageButtonState(button, button.dataset.languageOption === currentLocale);
  });
}

function clearLocaleSensitiveCache() {
  const storage = window.sessionStorage;
  if (!storage || typeof storage.length !== "number") {
    return;
  }

  const staleKeys = [];
  for (let index = 0; index < storage.length; index += 1) {
    const key = storage.key(index);
    if (typeof key === "string" && key.startsWith("anime-ops-ui-")) {
      staleKeys.push(key);
    }
  }
  staleKeys.forEach((key) => storage.removeItem(key));
}

document.addEventListener("DOMContentLoaded", () => {
  const body = document.body;
  if (!body) return;

  const cookieName = body.dataset.languageCookieName || "anime-ops-ui-lang";
  const currentLocale = body.dataset.locale || "zh-Hans";
  syncLanguageButtons(currentLocale);

  document.querySelectorAll("[data-language-option]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      const nextLocale = button.dataset.languageOption;
      if (!nextLocale || nextLocale === currentLocale) {
        return;
      }
      document.cookie = `${cookieName}=${nextLocale}; Max-Age=31536000; Path=/; SameSite=Lax`;
      clearLocaleSensitiveCache();
      window.location.reload();
    });
  });
});
