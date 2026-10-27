// Runs before styles and application startup to apply the saved appearance on first paint.
(() => {
  const key = "unified-appearance";
  const system = window.matchMedia("(prefers-color-scheme: dark)");
  const normalize = (value) => ["system", "light", "dark"].includes(value) ? value : "system";
  let mode = "system";
  let selector;
  try { mode = normalize(localStorage.getItem(key)); } catch {}
  function apply() {
    const dark = mode === "dark" || (mode === "system" && system.matches);
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    document.documentElement.dataset.themePreference = mode;
    document.documentElement.style.colorScheme = dark ? "dark" : "light";
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? "#101916" : "#f6f7f4");
    if (selector) selector.value = mode;
  }
  apply();
  system.addEventListener("change", apply);
  window.addEventListener("storage", (event) => {
    if (event.key === key || event.key === null) {
      mode = normalize(event.newValue);
      apply();
    }
  });
  document.addEventListener("DOMContentLoaded", () => {
    selector = document.getElementById("theme-mode");
    if (!selector) return;
    selector.value = mode;
    selector.addEventListener("change", () => {
      mode = normalize(selector.value);
      try { localStorage.setItem(key, mode); } catch {}
      apply();
    });
  });
})();
