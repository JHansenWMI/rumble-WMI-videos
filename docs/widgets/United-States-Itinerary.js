/**
 * United States Itinerary — render docs/united-states-itinerary.json
 * Loaded from CMS via:
 *   <script src="https://jhansenwmi.github.io/rumble-WMI-videos/widgets/United-States-Itinerary.js"></script>
 *
 * Mount (in CMS shell / page body):
 *   <div id="content"
 *        data-itinerary="https://jhansenwmi.github.io/rumble-WMI-videos/united-states-itinerary.json"></div>
 *
 * Year rows: click anywhere to expand/collapse. The two most recent years
 * default expanded; older years default collapsed.
 */
(function () {
  var DEFAULT_DATA =
    "https://jhansenwmi.github.io/rumble-WMI-videos/united-states-itinerary.json";
  var OPEN_YEAR_COUNT = 2;

  function dataUrl(container) {
    return (
      (container && container.getAttribute("data-itinerary")) || ""
    ).trim() || DEFAULT_DATA;
  }

  function findMount() {
    var el = document.getElementById("content");
    if (el) return el;
    return document.querySelector("[data-itinerary]");
  }

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, function (m) {
      return {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[m];
    });
  }

  function collectYears(events) {
    var years = [];
    var seen = {};
    for (var i = 0; i < events.length; i++) {
      var y = events[i].year;
      if (y == null || y === "") continue;
      var key = String(y);
      if (!seen[key]) {
        seen[key] = true;
        years.push(Number(y));
      }
    }
    return years;
  }

  /** Two most recent calendar years present in the data (changes as years roll). */
  function defaultOpenYears(years) {
    var sorted = years.slice().sort(function (a, b) {
      return b - a;
    });
    var open = {};
    for (var i = 0; i < sorted.length && i < OPEN_YEAR_COUNT; i++) {
      open[String(sorted[i])] = true;
    }
    return open;
  }

  function eventBodyHtml(ev) {
    if (ev.body_html) return ev.body_html;
    var parts = [];
    if (ev.flyer) {
      parts.push(
        '<img class="wmi-itinerary-flyer" src="' +
          escapeHtml(ev.flyer) +
          '" alt="' +
          escapeHtml(ev.flyer_alt || "") +
          '" style="width:200px;height:auto;" />'
      );
    }
    if (ev.place) {
      parts.push("<strong>" + escapeHtml(ev.place) + "</strong>");
    }
    if (ev.date_text) {
      parts.push(escapeHtml(ev.date_text));
    }
    if (ev.event_name) {
      parts.push(escapeHtml(ev.event_name));
    }
    if (ev.time_text) {
      parts.push(escapeHtml(ev.time_text));
    }
    if (ev.speakers && ev.speakers.length) {
      parts.push(escapeHtml(ev.speakers.join(", ")));
    }
    if (ev.hosts && ev.hosts.length) {
      parts.push("Host: " + escapeHtml(ev.hosts.join(", ")));
    }
    if (ev.venue) {
      parts.push(escapeHtml(ev.venue));
    }
    if (ev.address_lines && ev.address_lines.length) {
      parts.push(escapeHtml(ev.address_lines.join(", ")));
    }
    if (ev.body_lines && ev.body_lines.length) {
      parts.push(escapeHtml(ev.body_lines.join("\n")).replace(/\n/g, "<br />"));
    }
    return "<p>" + parts.join("<br />") + "</p>";
  }

  function setEventRowVisible(row, expanded) {
    // CMS theme CSS often forces tr { display: table-row }, which overrides
    // the HTML hidden attribute. Set display with !important instead.
    if (expanded) {
      row.style.removeProperty("display");
      row.removeAttribute("hidden");
      row.classList.remove("is-year-collapsed");
    } else {
      row.style.setProperty("display", "none", "important");
      row.setAttribute("hidden", "hidden");
      row.classList.add("is-year-collapsed");
    }
  }

  function setYearExpanded(table, year, expanded) {
    var yearKey = String(year);
    var header = table.querySelector(
      'tr.wmi-itinerary-year[data-year="' + yearKey + '"]'
    );
    if (!header) return;
    header.setAttribute("aria-expanded", expanded ? "true" : "false");
    header.classList.toggle("is-collapsed", !expanded);
    var indicator = header.querySelector(".wmi-itinerary-year-indicator");
    if (indicator) {
      indicator.textContent = expanded ? "\u25BE" : "\u25B8"; // ▾ ▸
      indicator.setAttribute(
        "aria-label",
        expanded ? "Collapse year" : "Expand year"
      );
    }

    // Hide/show event rows until the next year header (DOM order = year sections).
    var row = header.nextElementSibling;
    while (row) {
      if (
        row.classList &&
        row.classList.contains("wmi-itinerary-year")
      ) {
        break;
      }
      if (
        row.classList &&
        row.classList.contains("wmi-itinerary-event")
      ) {
        setEventRowVisible(row, expanded);
      } else if (row.tagName === "TR" || (row.tagName && row.tagName.toLowerCase() === "tr")) {
        // Fallback if class names were stripped by CMS HTML filter
        setEventRowVisible(row, expanded);
      }
      row = row.nextElementSibling;
    }
  }

  function toggleYear(table, year) {
    var header = table.querySelector(
      'tr.wmi-itinerary-year[data-year="' + String(year) + '"]'
    );
    if (!header) return;
    var expanded = header.getAttribute("aria-expanded") === "true";
    setYearExpanded(table, year, !expanded);
  }

  function isEventPosterImage(img) {
    if (!img || !img.tagName || img.tagName.toLowerCase() !== "img") {
      return false;
    }
    if (img.classList && img.classList.contains("wmi-itinerary-flag")) {
      return false;
    }
    var src = (img.getAttribute("src") || "").toLowerCase();
    if (
      src.indexOf("country-flags") >= 0 ||
      src.indexOf("state-flags") >= 0 ||
      src.indexOf("userfiles/flags") >= 0 ||
      /\/flags\//.test(src)
    ) {
      return false;
    }
    var cell = img.closest ? img.closest("td") : null;
    // First column is the flag cell
    if (cell && typeof cell.cellIndex === "number" && cell.cellIndex === 0) {
      return false;
    }
    var row = img.closest ? img.closest("tr.wmi-itinerary-event") : null;
    return !!row;
  }

  function ensurePosterLightbox() {
    var box = document.getElementById("wmi-poster-lightbox");
    if (box) return box;
    box = document.createElement("div");
    box.id = "wmi-poster-lightbox";
    box.className = "wmi-poster-lightbox";
    box.setAttribute("hidden", "hidden");
    box.setAttribute("aria-hidden", "true");
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-label", "Event poster");
    box.innerHTML =
      '<img class="wmi-poster-lightbox-img" alt="Event poster" src="" />' +
      '<p class="wmi-poster-lightbox-hint">Click anywhere to close</p>';
    document.body.appendChild(box);

    function closeLightbox() {
      box.setAttribute("hidden", "hidden");
      box.setAttribute("aria-hidden", "true");
      var img = box.querySelector(".wmi-poster-lightbox-img");
      if (img) img.removeAttribute("src");
      document.documentElement.classList.remove("wmi-poster-lightbox-open");
      document.body.classList.remove("wmi-poster-lightbox-open");
    }

    box.addEventListener("click", function () {
      closeLightbox();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !box.hasAttribute("hidden")) {
        closeLightbox();
      }
    });
    box._wmiClose = closeLightbox;
    return box;
  }

  function openPosterLightbox(src, alt) {
    if (!src) return;
    var box = ensurePosterLightbox();
    var img = box.querySelector(".wmi-poster-lightbox-img");
    if (img) {
      img.src = src;
      img.alt = alt || "Event poster";
    }
    box.removeAttribute("hidden");
    box.setAttribute("aria-hidden", "false");
    document.documentElement.classList.add("wmi-poster-lightbox-open");
    document.body.classList.add("wmi-poster-lightbox-open");
  }

  function wireYearToggles(container) {
    var table = container.querySelector("table.wmi-itinerary-table");
    if (!table) return;
    table.addEventListener("click", function (e) {
      // Poster enlarge: body-cell images only (not flags)
      var img = e.target && e.target.closest ? e.target.closest("img") : null;
      if (img && table.contains(img) && isEventPosterImage(img)) {
        e.preventDefault();
        e.stopPropagation();
        openPosterLightbox(
          img.currentSrc || img.src,
          img.getAttribute("alt") || "Event poster"
        );
        return;
      }
      var row = e.target.closest
        ? e.target.closest("tr.wmi-itinerary-year")
        : null;
      if (!row || !table.contains(row)) return;
      e.preventDefault();
      toggleYear(table, row.getAttribute("data-year"));
    });
    // Keyboard: Enter/Space on focused year row
    table.addEventListener("keydown", function (e) {
      if (e.key !== "Enter" && e.key !== " ") return;
      var row = e.target.closest
        ? e.target.closest("tr.wmi-itinerary-year")
        : null;
      if (!row || !table.contains(row)) return;
      e.preventDefault();
      toggleYear(table, row.getAttribute("data-year"));
    });
  }

  function markPosterThumbs(container) {
    var imgs = container.querySelectorAll(
      "tr.wmi-itinerary-event td:nth-child(2) img"
    );
    for (var i = 0; i < imgs.length; i++) {
      if (isEventPosterImage(imgs[i])) {
        imgs[i].classList.add("wmi-itinerary-poster-thumb");
        if (!imgs[i].getAttribute("title")) {
          imgs[i].setAttribute("title", "Click to enlarge poster");
        }
      }
    }
  }

  function render(container, data) {
    var html = [];
    if (data.introHtml) {
      html.push('<div class="wmi-itinerary-intro">' + data.introHtml + "</div>");
    }
    html.push('<table class="events-list wmi-itinerary-table"><tbody>');

    var events = data.events || [];
    var years = collectYears(events);
    var openYears = defaultOpenYears(years);
    var lastYear = null;

    for (var i = 0; i < events.length; i++) {
      var ev = events[i];
      var year = ev.year;
      if (year != null && year !== lastYear) {
        lastYear = year;
        var yearKey = String(year);
        var expanded = !!openYears[yearKey];
        html.push(
          '<tr class="wmi-itinerary-year' +
            (expanded ? "" : " is-collapsed") +
            '" data-year="' +
            escapeHtml(yearKey) +
            '" role="button" tabindex="0" aria-expanded="' +
            (expanded ? "true" : "false") +
            '">' +
            "<td>&nbsp;</td>" +
            "<td>" +
            '<h3 class="wmi-itinerary-year-heading">' +
            '<span class="wmi-itinerary-year-indicator" aria-hidden="true">' +
            (expanded ? "\u25BE" : "\u25B8") +
            "</span> " +
            "<strong>" +
            escapeHtml(yearKey) +
            "</strong>" +
            "</h3>" +
            "</td>" +
            "</tr>"
        );
      }

      var yearAttr =
        year != null && year !== ""
          ? String(year)
          : lastYear != null
            ? String(lastYear)
            : "";
      var expandedEv = yearAttr ? !!openYears[yearAttr] : true;
      // Inline display for first paint (beats CMS tr{display:table-row} rules)
      var hideStyle = expandedEv
        ? ""
        : ' style="display:none !important" hidden';

      var flagCell = "&nbsp;";
      if (ev.flag) {
        flagCell =
          '<img class="wmi-itinerary-flag" alt="' +
          escapeHtml(ev.flag_alt || "") +
          '" src="' +
          escapeHtml(ev.flag) +
          '" border="0" />';
      }

      var body = eventBodyHtml(ev);
      html.push(
        '<tr class="wmi-itinerary-event' +
          (expandedEv ? "" : " is-year-collapsed") +
          '" data-id="' +
          escapeHtml(ev.id || "") +
          '" data-year="' +
          escapeHtml(yearAttr) +
          '"' +
          hideStyle +
          ">" +
          "<td>" +
          flagCell +
          "</td>" +
          "<td>" +
          body +
          "</td>" +
          "</tr>"
      );
    }

    html.push("</tbody></table>");
    if (!events.length) {
      html.push('<p class="wmi-itinerary-empty">No itinerary events loaded.</p>');
    }

    container.innerHTML = html.join("\n");
    container.classList.add("wmi-itinerary-ready");
    markPosterThumbs(container);
    wireYearToggles(container);
  }

  function showError(container, msg) {
    container.innerHTML =
      '<p class="wmi-itinerary-error">Could not load itinerary: ' +
      escapeHtml(msg) +
      "</p>";
  }

  function boot() {
    var container = findMount();
    if (!container) return;
    var url = dataUrl(container);
    container.innerHTML = '<p class="wmi-itinerary-loading">Loading itinerary…</p>';

    fetch(url, { credentials: "omit", cache: "no-cache" })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status + " for " + url);
        return res.json();
      })
      .then(function (data) {
        render(container, data || {});
      })
      .catch(function (err) {
        showError(container, err && err.message ? err.message : String(err));
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
