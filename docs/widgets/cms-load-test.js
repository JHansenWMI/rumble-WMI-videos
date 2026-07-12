/**
 * One-time CMS load test for remote CSS/JS + cross-origin fetch.
 * Loaded via <script src="…github.io/…/cms-load-test.js"> from a CMS test page.
 */
(function () {
  var ROOT_ID = "wmi-cms-load-test";
  var DEFAULT_FEED =
    "https://jhansenwmi.github.io/rumble-WMI-videos/rumble-feed.json";

  function el(id) {
    return document.getElementById(id);
  }

  function setRow(id, ok, detail) {
    var row = el(id);
    if (!row) return;
    row.className =
      "wmi-cms-load-test-row " + (ok ? "wmi-ok" : "wmi-fail");
    row.textContent = (ok ? "PASS: " : "FAIL: ") + detail;
  }

  function ensureShell() {
    var root = el(ROOT_ID);
    if (!root) {
      root = document.createElement("div");
      root.id = ROOT_ID;
      document.body.appendChild(root);
    }
    if (!root.querySelector(".wmi-cms-load-test-title")) {
      root.innerHTML =
        '<p class="wmi-cms-load-test-title">WMI CMS load test</p>' +
        '<div id="wmi-cms-test-js" class="wmi-cms-load-test-row wmi-pending">… JS</div>' +
        '<div id="wmi-cms-test-css" class="wmi-cms-load-test-row wmi-pending">… CSS</div>' +
        '<div id="wmi-cms-test-fetch" class="wmi-cms-load-test-row wmi-pending">… fetch JSON</div>' +
        '<div id="wmi-cms-test-note" class="wmi-cms-load-test-row wmi-pending"></div>';
    }
    return root;
  }

  function cssLooksApplied(root) {
    try {
      var cs = window.getComputedStyle(root);
      // From cms-load-test.css: green border + mint background
      var border = (cs.borderTopColor || "").replace(/\s/g, "");
      var bg = (cs.backgroundColor || "").replace(/\s/g, "");
      // rgb(0, 170, 119) ≈ #0a7 ; rgb(232, 255, 242) ≈ #e8fff2
      var borderOk =
        border === "rgb(0,170,119)" ||
        border === "rgba(0,170,119,1)" ||
        /0,\s*170,\s*119/.test(cs.borderTopColor || "");
      var bgOk =
        bg === "rgb(232,255,242)" ||
        bg === "rgba(232,255,242,1)" ||
        /232,\s*255,\s*242/.test(cs.backgroundColor || "");
      return borderOk || bgOk;
    } catch (e) {
      return false;
    }
  }

  function run() {
    var root = ensureShell();
    setRow(
      "wmi-cms-test-js",
      true,
      "external <script src> ran (this file executed)"
    );

    if (cssLooksApplied(root)) {
      setRow(
        "wmi-cms-test-css",
        true,
        "external stylesheet applied (green box styles visible)"
      );
    } else {
      setRow(
        "wmi-cms-test-css",
        false,
        "stylesheet missing or stripped — expect green border + mint background. " +
          "If the box is plain, CMS blocked <link rel=stylesheet>."
      );
    }

    var feedUrl =
      (root.getAttribute("data-feed") || DEFAULT_FEED).trim() || DEFAULT_FEED;
    var note = el("wmi-cms-test-note");
    if (note) {
      note.className = "wmi-cms-load-test-row wmi-pending";
      note.textContent = "Feed URL: " + feedUrl;
    }

    if (typeof fetch !== "function") {
      setRow("wmi-cms-test-fetch", false, "fetch() not available in this browser");
      return;
    }

    fetch(feedUrl, { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (data) {
        var n =
          data && typeof data.itemCount === "number"
            ? data.itemCount
            : data && Array.isArray(data.items)
              ? data.items.length
              : "?";
        var title = (data && data.title) || "(no title)";
        setRow(
          "wmi-cms-test-fetch",
          true,
          "fetch JSON OK — title=" +
            title +
            ", items≈" +
            n +
            " (cross-origin from CMS → github.io)"
        );
      })
      .catch(function (err) {
        setRow(
          "wmi-cms-test-fetch",
          false,
          "fetch failed (CORS, network, or blocked): " +
            (err && err.message ? err.message : String(err))
        );
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
