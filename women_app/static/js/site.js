document.addEventListener("DOMContentLoaded", () => {
  const switcher = document.getElementById("languageSwitcher");
  const comfortButtons = Array.from(document.querySelectorAll("[data-comfort-toggle], #comfortToggle"));
  const themeToggle = document.querySelector("[data-theme-toggle]");
  const navToggle = document.getElementById("navToggle");
  const headerPanel = document.getElementById("headerPanel");
  const uiStringsElement = document.getElementById("uiStrings");
  const uiStrings = uiStringsElement ? JSON.parse(uiStringsElement.textContent) : {};
  const themeMeta = document.querySelector('meta[name="theme-color"]');

  function setTheme(theme) {
    const normalized = theme === "dark" ? "dark" : "light";
    document.body.dataset.theme = normalized;
    window.localStorage.setItem("jan-setu-theme", normalized);

    if (themeToggle) {
      themeToggle.classList.toggle("active-ghost", normalized === "dark");
      const nextLabel = normalized === "dark" ? "Switch to light theme" : "Switch to dark theme";
      const labelNode = themeToggle.querySelector("[data-theme-label]");
      if (labelNode) {
        labelNode.textContent = nextLabel;
      }
      themeToggle.setAttribute("aria-label", nextLabel);
      themeToggle.setAttribute("title", nextLabel);
    }

    if (themeMeta) {
      themeMeta.setAttribute("content", normalized === "dark" ? "#091120" : "#eef3ff");
    }
  }

  function renderComfortMode() {
    const enabled = window.localStorage.getItem("ai-sakhi-comfort-mode") === "1";
    document.body.classList.toggle("ui-large", enabled);
    comfortButtons.forEach((button) => {
      button.classList.toggle("active-ghost", enabled);
      button.textContent = enabled ? (uiStrings.comfort_on || "A- Text") : (uiStrings.comfort_off || "A+ Text");
    });
  }

  function closeMobilePanel() {
    if (!headerPanel || !navToggle) {
      return;
    }
    headerPanel.classList.remove("is-open");
    navToggle.setAttribute("aria-expanded", "false");
  }

  if (switcher) {
    switcher.addEventListener("change", () => {
      const url = new URL(window.location.href);
      url.searchParams.set("lang", switcher.value);
      window.location.href = url.toString();
    });
  }

  comfortButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const enabled = window.localStorage.getItem("ai-sakhi-comfort-mode") === "1";
      window.localStorage.setItem("ai-sakhi-comfort-mode", enabled ? "0" : "1");
      renderComfortMode();
    });
  });

  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const nextTheme = document.body.dataset.theme === "dark" ? "light" : "dark";
      setTheme(nextTheme);
    });
  }

  if (navToggle && headerPanel) {
    navToggle.addEventListener("click", () => {
      const nextState = !headerPanel.classList.contains("is-open");
      headerPanel.classList.toggle("is-open", nextState);
      navToggle.setAttribute("aria-expanded", nextState ? "true" : "false");
    });

    headerPanel.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", closeMobilePanel);
    });

    window.addEventListener("resize", () => {
      if (window.innerWidth > 980) {
        closeMobilePanel();
      }
    });
  }

  setTheme(window.localStorage.getItem("jan-setu-theme") || "light");
  renderComfortMode();
});
