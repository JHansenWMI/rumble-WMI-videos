/**
 * Warning Social Media Video — main Rumble grid widget.
 * Loaded from CMS via:
 *   <script src="https://jhansenwmi.github.io/rumble-WMI-videos/widgets/Warning-Social-Media-Video.js"></script>
 *
 * Mount (in CMS shell):
 *   <div id="rumbleGridWidget" class="rw-root"
 *        data-feed="https://jhansenwmi.github.io/rumble-WMI-videos/rumble-feed.json"
 *        data-limit="30">
 *     <div class="rw-status" id="rwStatus">Loading videos…</div>
 *     <div class="rw-grid" id="rwGrid" style="display: none;"></div>
 *   </div>
 */
(function () {
  var DEFAULT_FEED =
    "https://jhansenwmi.github.io/rumble-WMI-videos/rumble-feed.json";
  var DEFAULT_LIMIT = 30;
  var RUMBLE_MODAL_Z_INDEX = 10000;

  var CHANNEL_WARNING_TV = "WARNING TV - Jonathan Hansen";
  var CHANNEL_BROADCAST_HISTORY = "WMI TV Broadcast History";

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

  function getPubDate(item) {
    return item && item.pubDate ? String(item.pubDate) : "";
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

  function channelNameOf(item) {
    return item && item.channelName ? String(item.channelName).trim() : "";
  }

  function shouldExclude(item) {
    var source = item && item.sourcePage ? String(item.sourcePage) : "";
    var ch = channelNameOf(item);
    if (/\/shorts(\/|$)/i.test(source) && /The Overcoming Women$/i.test(ch)) {
      return true;
    }
    return false;
  }

  function isTVShowItem(item) {
    var title = item && item.title ? String(item.title) : "";
    return /TV\d{8}\s*$/i.test(title);
  }

  // Channel-specific TV rules (feed generator unchanged; display-only):
  // - WMI TV Broadcast History + TV{date}: hide here; still on TV shows page.
  // - WARNING TV + TV{date}: show here; strip TV{date}; date from pubDate.
  function shouldShowInCmsGrid(item) {
    if (shouldExclude(item)) return false;
    if (!isTVShowItem(item)) return true;
    var ch = channelNameOf(item);
    if (ch === CHANNEL_BROADCAST_HISTORY) return false;
    if (ch === CHANNEL_WARNING_TV) return true;
    return false;
  }

  function sortByDateDesc(a, b) {
    var da = new Date(getPubDate(a)).getTime();
    var db = new Date(getPubDate(b)).getTime();
    return (isNaN(db) ? -Infinity : db) - (isNaN(da) ? -Infinity : da);
  }

  function ensureRumbleEmbedScript() {
    if (window.Rumble && typeof window.Rumble === "function") return;
    // Official Rumble embed stub — loads embedJS on first Rumble("play", …)
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
    var root = document.getElementById("rumbleGridWidget");
    if (!root) {
      console.warn(
        "Warning-Social-Media-Video: #rumbleGridWidget not found; skip."
      );
      return;
    }

    var statusEl = document.getElementById("rwStatus");
    var gridEl = document.getElementById("rwGrid");
    if (!statusEl || !gridEl) {
      if (!statusEl) {
        statusEl = document.createElement("div");
        statusEl.id = "rwStatus";
        statusEl.className = "rw-status";
        statusEl.textContent = "Loading videos…";
        root.appendChild(statusEl);
      }
      if (!gridEl) {
        gridEl = document.createElement("div");
        gridEl.id = "rwGrid";
        gridEl.className = "rw-grid";
        gridEl.style.display = "none";
        root.appendChild(gridEl);
      }
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
          statusEl.textContent = "No items loaded.";
          console.error("Feed load errors:", errors);
          return;
        }

        items = items.filter(shouldShowInCmsGrid);
        items.sort(sortByDateDesc);
        items = items.slice(0, limit);

        var html = items
          .map(function (item) {
            var title = normalizeTitle(item.title);
            var link = getLink(item);
            var thumb = getThumb(item);
            var date = formatDateLA(getPubDate(item));
            var videoId = getVideoId(item);
            var shortClass = isShort(item) ? " rw-card--short" : "";
            var thumbStyle = thumb
              ? ' style="--rw-thumb-bg: url(\'' +
                escapeHtml(thumb) +
                "')\""
              : "";

            return (
              '<div class="rw-card' +
              shortClass +
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
          statusEl.textContent = "Loaded videos (one or more feeds failed).";
          console.warn("Some feeds failed:", errors);
        } else {
          statusEl.style.display = "none";
        }
      })
      .catch(function (err) {
        statusEl.textContent = "Failed to load videos. Check console for details.";
        console.error(err);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
