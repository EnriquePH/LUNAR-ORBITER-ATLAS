// Language switch for the project page: ?lang= wins, then the saved choice,
// then the browser language. Storage may be unavailable, so it is guarded.
(function () {
  const KEY = "lunar-orbiter-lang";
  const SUPPORTED = ["en", "es"];

  function saved() {
    try { return window.localStorage.getItem(KEY); } catch (error) { return null; }
  }

  function initial() {
    const fromUrl = new URLSearchParams(window.location.search).get("lang");
    const browser = (navigator.language || "en").slice(0, 2).toLowerCase();
    return [fromUrl, saved(), browser].find((lang) => SUPPORTED.includes(lang)) || "en";
  }

  function apply(lang) {
    const root = document.documentElement;
    root.lang = lang;
    root.dataset.lang = lang;
    document.querySelectorAll("[data-set-lang]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.setLang === lang));
    });
  }

  apply(initial());
  document.querySelectorAll("[data-set-lang]").forEach((button) => {
    button.addEventListener("click", () => {
      const lang = button.dataset.setLang;
      apply(lang);
      try { window.localStorage.setItem(KEY, lang); } catch (error) {}
    });
  });
})();
