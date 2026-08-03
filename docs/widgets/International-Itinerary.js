/**
 * International Itinerary — render docs/international-itinerary.json
 * Loaded from CMS via:
 *   <script src="https://jhansenwmi.github.io/rumble-WMI-videos/widgets/International-Itinerary.js"></script>
 *
 * Mount (in CMS shell / page body):
 *   <div id="content"
 *        data-itinerary="https://jhansenwmi.github.io/rumble-WMI-videos/international-itinerary.json"></div>
 */
(function () {
  var DEFAULT_DATA =
    "https://jhansenwmi.github.io/rumble-WMI-videos/international-itinerary.json";

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

  function render(container, data) {
    var html = [];
    if (data.introHtml) {
      html.push('<div class="wmi-itinerary-intro">' + data.introHtml + "</div>");
    }
    html.push('<table class="events-list wmi-itinerary-table"><tbody>');

    var events = data.events || [];
    var lastYear = null;
    for (var i = 0; i < events.length; i++) {
      var ev = events[i];
      var year = ev.year;
      if (year != null && year !== lastYear) {
        lastYear = year;
        html.push(
          "<tr class=\"wmi-itinerary-year\">" +
            "<td>&nbsp;</td>" +
            "<td><h3><strong>" +
            escapeHtml(String(year)) +
            "</strong></h3></td>" +
            "</tr>"
        );
      }

      var flagCell = "&nbsp;";
      if (ev.flag) {
        flagCell =
          '<img class="wmi-itinerary-flag" alt="' +
          escapeHtml(ev.flag_alt || "") +
          '" src="' +
          escapeHtml(ev.flag) +
          '" border="0" />';
      }

      // Prefer preserved CMS cell HTML for visual fidelity of the seed scrape.
      var body = ev.body_html;
      if (!body) {
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
        body = "<p>" + parts.join("<br />") + "</p>";
      }

      html.push(
        '<tr class="wmi-itinerary-event" data-id="' +
          escapeHtml(ev.id || "") +
          '">' +
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
