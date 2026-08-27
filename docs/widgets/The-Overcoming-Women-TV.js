/**
 * The Overcoming Women TV — Rumble grid widget.
 * Loaded from CMS via:
 *   <script src="https://jhansenwmi.github.io/rumble-WMI-videos/widgets/The-Overcoming-Women-TV.js"></script>
 *
 * Mount (in CMS shell):
 *   <div id="overcomingRumbleGridWidget" class="rw-root"
 *        data-feed="https://jhansenwmi.github.io/rumble-WMI-videos/overcoming-feed.json"
 *        data-limit="30">
 *     <div class="rw-status" id="owRwStatus">Loading videos…</div>
 *     <div class="rw-grid" id="owRwGrid" style="display: none;"></div>
 *   </div>
 *
 * Dates: prefer TV{YYYYMMDD} air date from title/link (snap to Friday); else pubDate.
 */
(function () {
  var DEFAULT_FEED =
    "https://jhansenwmi.github.io/rumble-WMI-videos/overcoming-feed.json";
  var DEFAULT_LIMIT = 30;
  var RUMBLE_MODAL_Z_INDEX = 10000;
  var ROOT_ID = "overcomingRumbleGridWidget";
  var STATUS_ID = "owRwStatus";
  var GRID_ID = "owRwGrid";

  var dateFmt = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Los_Angeles",
    month: "short",
    day: "2-digit",
    year: "numeric",
  });

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

  function stripTrailingDate(title) {
    var re =
      /\s*-\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}(?:st|nd|rd|th)?(?:,)?\s+\d{4}\s*$/i;
    return title.replace(re, "").trim();
  }

  function stripTVSuffix(title) {
    return title.replace(/\s*TV\d{8}\s*$/i, "").trim();
  }

  function normalizeTitle(t) {
    var s = String(t || "").replace(/\s+/g, " ").trim();
    s = stripTVSuffix(s);
    s = stripTrailingDate(s);
    return s;
  }

  function formatDateLA(pubDateStr) {
    var d = new Date(pubDateStr);
    if (isNaN(d.getTime())) return "";
    return dateFmt.format(d);
  }

  function getPubDate(item) {
    return item && item.pubDate ? String(item.pubDate) : "";
  }

  function getScheduledTime(item) {
    return item && item.scheduledTime ? String(item.scheduledTime) : "";
  }

  function isUpcoming(item) {
    var raw = getScheduledTime(item);
    if (!raw) return false;
    var d = new Date(raw);
    return !isNaN(d.getTime()) && d.getTime() > Date.now();
  }

  function formatStartsLA(scheduledStr) {
    var d = new Date(scheduledStr);
    if (isNaN(d.getTime())) return "";
    var datePart = new Intl.DateTimeFormat("en-US", {
      timeZone: "America/Los_Angeles",
      month: "short",
      day: "numeric",
    }).format(d);
    var timePart = new Intl.DateTimeFormat("en-US", {
      timeZone: "America/Los_Angeles",
      hour: "numeric",
      minute: "2-digit",
    }).format(d);
    return "Starts " + datePart + ", " + timePart;
  }

  function getTVDateMatch(item) {
    var text = item && item.title ? String(item.title) : "";
    var m = text.match(/TV(\d{4})(\d{2})(\d{2})\s*$/i);
    if (!m && item && item.link) {
      text = String(item.link);
      m = text.match(/tv(\d{4})(\d{2})(\d{2})\b/i);
    }
    return m;
  }

  function getTVAirDate(item) {
    var m = getTVDateMatch(item);
    if (!m) return null;
    var y = +m[1];
    var mo = +m[2];
    var d = +m[3];
    var dt = new Date(Date.UTC(y, mo - 1, d, 12, 0, 0));
    var dow = dt.getUTCDay();
    if (dow === 5) return dt;
    var toPrev = (dow - 5 + 7) % 7;
    var toNext = (5 - dow + 7) % 7;
    var delta = toPrev <= toNext ? -toPrev : toNext;
    dt.setUTCDate(dt.getUTCDate() + delta);
    return dt;
  }

  function getTVAirDateStr(item) {
    if (isUpcoming(item)) return formatStartsLA(getScheduledTime(item));
    var dt = getTVAirDate(item);
    if (!dt) return formatDateLA(getPubDate(item));
    return dateFmt.format(dt);
  }

  function getTVAirTimestamp(item) {
    var dt = getTVAirDate(item);
    if (!dt) return new Date(getPubDate(item)).getTime();
    return dt.getTime();
  }

  function getThumb(item) {
    return item && item["media:content"] ? String(item["media:content"]) : "";
  }

  function getLink(item) {
    return item && item.link ? String(item.link) : "#";
  }

  function getVideoId(item) {
    if (item && item.videoId) return String(item.videoId);
    var link = item && item.link ? String(item.link) : "";
    var m = link.match(/\/(v[a-z0-9]+)-/);
    return m ? m[1] : "";
  }

  function isShort(item) {
    var link = getLink(item);
    var source = item && item.sourcePage ? String(item.sourcePage) : "";
    var title = item && item.title ? String(item.title) : "";
    return (
      /\/shorts(\/|$)/i.test(link) ||
      /\/shorts(\/|$)/i.test(source) ||
      /#shorts\b/i.test(title)
    );
  }

  function sortByDateDesc(a, b) {
    var da = getTVAirTimestamp(a);
    var db = getTVAirTimestamp(b);
    return (isNaN(db) ? -Infinity : db) - (isNaN(da) ? -Infinity : da);
  }

  function ensureRumbleEmbedScript() {
    if (window.Rumble && typeof window.Rumble === "function") return;
    (function (r, u, m, b, l, e) {
      r._Rumble = b;
      r[b] ||
        (r[b] = function () {
          (r[b]._ = r[b]._ || []).push(arguments);
          if (r[b]._.length == 1) {
            l = u.createElement(m);
            e = u.getElementsByTagName(m)[0];
            l.async = 1;
            l.src =
              "https://rumble.com/embedJS/uhau7j" +
              (arguments[1] && arguments[1].video
                ? "." + arguments[1].video
                : "") +
              "/?url=" +
              encodeURIComponent(location.href) +
              "&args=" +
              encodeURIComponent(JSON.stringify([].slice.apply(arguments)));
            e.parentNode.insertBefore(l, e);
          }
        });
    })(window, document, "script", "Rumble");
  }

  function ensureRumbleModal() {
    var modal = document.getElementById("rumbleModal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "rumbleModal";
    modal.setAttribute("style", "display: none;");
    modal.innerHTML =
      '<div class="rumbleModalContent">' +
      '<div class="rumbleModalBar">' +
      '<button type="button" id="rumbleModalClose" aria-label="Close">&times;</button>' +
      "</div>" +
      '<div id="rumblePlayerWrap"></div>' +
      "</div>";
    document.body.appendChild(modal);
    return modal;
  }

  function ensureRumbleModalPortal() {
    var modal = ensureRumbleModal();
    if (modal.parentNode !== document.body) {
      document.body.appendChild(modal);
    }
    modal.style.zIndex = String(RUMBLE_MODAL_Z_INDEX);
    return modal;
  }

  var rumbleModalHandlersWired = false;

  function closeRumbleOverlay() {
    var modal = document.getElementById("rumbleModal");
    var wrap = document.getElementById("rumblePlayerWrap");
    if (modal) modal.style.display = "none";
    if (wrap) wrap.innerHTML = "";
  }

  function wireRumbleModalHandlers() {
    if (rumbleModalHandlersWired) return;
    var modal = ensureRumbleModalPortal();
    var closeBtn = document.getElementById("rumbleModalClose");
    if (!modal || !closeBtn) return;
    rumbleModalHandlersWired = true;
    closeBtn.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      closeRumbleOverlay();
    });
    modal.addEventListener("click", function (e) {
      if (e.target === modal) closeRumbleOverlay();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") return;
      var m = document.getElementById("rumbleModal");
      if (m && m.style.display === "flex") closeRumbleOverlay();
    });
  }

  function showRumbleOverlay(videoCode) {
    if (!videoCode) return;
    ensureRumbleEmbedScript();
    wireRumbleModalHandlers();
    var modal = ensureRumbleModalPortal();
    if (!modal) return;
    var wrap = document.getElementById("rumblePlayerWrap");
    if (!wrap) return;
    var playerId =
      "rumble_embed_" + String(videoCode).replace(/[^a-z0-9]/gi, "");
    wrap.innerHTML =
      '<div id="' +
      playerId +
      '" style="width:100%; aspect-ratio:16/9; min-height: 300px;"></div>';
    modal.style.display = "flex";
    var doPlay = function () {
      if (window.Rumble && typeof window.Rumble === "function") {
        try {
          window.Rumble("play", { video: videoCode, div: playerId });
        } catch (err) {
          console.warn("Rumble play error", err);
        }
      } else {
        setTimeout(doPlay, 250);
      }
    };
    setTimeout(doPlay, 60);
  }

  function attachCardClicks(gridEl) {
    gridEl.querySelectorAll(".rw-card[data-video-id]").forEach(function (card) {
      var videoId = card.getAttribute("data-video-id");
      if (!videoId) return;
      var openPlayer = function (e) {
        if (e && (e.metaKey || e.ctrlKey || e.shiftKey)) {
          var lnk = card.getAttribute("data-link");
          if (lnk) window.open(lnk, "_blank");
          return;
        }
        if (e) e.preventDefault();
        showRumbleOverlay(videoId);
      };
      card.style.cursor = "pointer";
      card.addEventListener("click", openPlayer);
    });
  }

  function parseLimit(root) {
    var raw = root.getAttribute("data-limit");
    var n = raw ? parseInt(raw, 10) : DEFAULT_LIMIT;
    if (isNaN(n) || n < 1) return DEFAULT_LIMIT;
    return n;
  }

  function feedUrls(root) {
    var single = (root.getAttribute("data-feed") || "").trim();
    if (single) return [single];
    var multi = (root.getAttribute("data-feeds") || "").trim();
    if (multi) {
      return multi
        .split(",")
        .map(function (s) {
          return s.trim();
        })
        .filter(Boolean);
    }
    return [DEFAULT_FEED];
  }

  function fetchFeed(url) {
    return fetch(url, { cache: "no-store" }).then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status + " for " + url);
      return res.json();
    });
  }

  function run() {
    var root = document.getElementById(ROOT_ID);
    if (!root) {
      console.warn(
        "The-Overcoming-Women-TV: #" + ROOT_ID + " not found; skip."
      );
      return;
    }

    var statusEl = document.getElementById(STATUS_ID);
    var gridEl = document.getElementById(GRID_ID);
    if (!statusEl) {
      statusEl = document.createElement("div");
      statusEl.id = STATUS_ID;
      statusEl.className = "rw-status";
      statusEl.textContent = "Loading videos…";
      root.appendChild(statusEl);
    }
    if (!gridEl) {
      gridEl = document.createElement("div");
      gridEl.id = GRID_ID;
      gridEl.className = "rw-grid";
      gridEl.style.display = "none";
      root.appendChild(gridEl);
    }

    ensureRumbleEmbedScript();
    wireRumbleModalHandlers();

    var feeds = feedUrls(root);
    var limit = parseLimit(root);

    Promise.allSettled(feeds.map(fetchFeed))
      .then(function (results) {
        var items = [];
        var errors = [];

        results.forEach(function (r) {
          if (r.status === "fulfilled") {
            var data = r.value;
            if (data && Array.isArray(data.items)) {
              items = items.concat(data.items);
            }
          } else {
            errors.push(r.reason);
          }
        });

        if (items.length === 0) {
          statusEl.textContent = "No videos loaded.";
          console.error("Feed load errors:", errors);
          return;
        }

        items.sort(sortByDateDesc);
        items = items.slice(0, limit);

        var html = items
          .map(function (item) {
            var title = normalizeTitle(item.title);
            var link = getLink(item);
            var thumb = getThumb(item);
            var date = getTVAirDateStr(item);
            var videoId = getVideoId(item);
            var shortClass = isShort(item) ? " rw-card--short" : "";
            var upcoming = isUpcoming(item);
            var thumbStyle = thumb
              ? ' style="--rw-thumb-bg: url(\'' +
                escapeHtml(thumb) +
                "')\""
              : "";

            return (
              '<div class="rw-card' +
              shortClass +
              (upcoming ? " rw-card--upcoming" : "") +
              '" data-video-id="' +
              escapeHtml(videoId) +
              '" data-link="' +
              escapeHtml(link) +
              '">' +
              '<div class="rw-thumbWrap"' +
              thumbStyle +
              ">" +
              (thumb
                ? '<img class="rw-thumb" src="' + escapeHtml(thumb) + '" >'
                : "") +
              (upcoming
                ? '<span class="rw-badge rw-badge--upcoming">UPCOMING</span>'
                : "") +
              "</div>" +
              '<div class="rw-meta">' +
              '<div class="rw-title">' +
              escapeHtml(title || "Untitled") +
              "</div>" +
              '<div class="rw-date">' +
              escapeHtml(date) +
              "</div>" +
              "</div>" +
              "</div>"
            );
          })
          .join("");

        gridEl.innerHTML = html;
        gridEl.style.display = "grid";
        attachCardClicks(gridEl);

        if (errors.length) {
          statusEl.textContent =
            "Loaded videos, but one or more feeds failed.";
          console.warn("Some feeds failed:", errors);
        } else {
          statusEl.style.display = "none";
        }
      })
      .catch(function (err) {
        statusEl.textContent =
          "Failed to load videos. Check console for details.";
        console.error(err);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
