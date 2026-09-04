// Display theme, applied before the first paint so a dark choice never flashes light.
// The choice ("light", "dark" or "system") lives in this browser's localStorage only; when storage
// is unavailable (private windows, locked-down browsers) the page simply stays light.
(function () {
  var KEY = "labelcheck-theme";
  function stored() {
    try { return localStorage.getItem(KEY) || "light"; } catch (e) { return "light"; }
  }
  function resolve(choice) {
    if (choice === "system") {
      return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    return choice === "dark" ? "dark" : "light";
  }
  function apply(choice) {
    var c = choice || stored();
    document.documentElement.dataset.themeChoice = c;
    document.documentElement.dataset.theme = resolve(c);
  }
  apply();
  // Print on white: a dark display would print as light text on white paper wherever background
  // printing is off. The page prints light and returns to the chosen display afterwards.
  window.addEventListener("beforeprint", function () { document.documentElement.dataset.theme = "light"; });
  window.addEventListener("afterprint", function () { apply(); });
  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () { apply(); });
  }
  window.lcApplyTheme = function (choice) {
    if (choice) { try { localStorage.setItem(KEY, choice); } catch (e) { /* stays for this page only */ } }
    apply(choice);
  };
})();
