/**
 * Warning TV Broadcasts — schedule list matched to tv-feed.json.
 * Loaded from CMS via:
 *   <script src="https://jhansenwmi.github.io/rumble-WMI-videos/widgets/Warning-TV-Broadcasts.js"></script>
 *
 * Mount (in CMS shell):
 *   <div id="content"
 *        data-feed="https://jhansenwmi.github.io/rumble-WMI-videos/tv-feed.json"
 *        data-schedule="https://jhansenwmi.github.io/rumble-WMI-videos/tv-schedule.txt"></div>
 *
 * Matching:
 * - Titles ending TV{YYYYMMDD}: match schedule by air date (not Rumble pubDate).
 * - WMI TV Broadcast History without TV{date}: match by normalized title;
 *   display date from tv-schedule.txt.
 * - No video: if a site thumb exists for the schedule air date
 *   ({base}/YYYYMMDD.jpg), show a non-clickable card that looks like
 *   the video rows. Bases tried in order (first image that loads wins):
 *     1) GitHub Pages docs/tv-thumbs/  (preferred for new work)
 *     2) CMS Userfiles/video-thumbs/   (legacy / already-hosted)
 *   Optional on #content:
 *     data-thumb-base="…"   — single base only (replaces the default list)
 *     data-thumb-bases="url1,url2" — custom ordered list of bases
 */
(function () {
  var DEFAULT_FEED =
    "https://jhansenwmi.github.io/rumble-WMI-videos/tv-feed.json";
  var DEFAULT_SCHEDULE =
    "https://jhansenwmi.github.io/rumble-WMI-videos/tv-schedule.txt";
  /** Preferred first; CMS fallback so existing Userfiles thumbs keep working. */
  var DEFAULT_THUMB_BASES = [
    "https://jhansenwmi.github.io/rumble-WMI-videos/tv-thumbs/",
    "https://www.worldministries.org/Userfiles/video-thumbs/",
  ];
  var RUMBLE_MODAL_Z_INDEX = 10000;
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
    var dt = getTVAirDate(item);
    if (!dt) return "";
    return dateFmt.format(dt);
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

  function channelNameOf(item) {
    return item && item.channelName ? String(item.channelName).trim() : "";
  }

  function isTVShowItem(item) {
    var title = item && item.title ? String(item.title) : "";
    return /TV\d{8}\s*$/i.test(title);
  }

  function isBroadcastHistoryChannel(item) {
    return channelNameOf(item) === CHANNEL_BROADCAST_HISTORY;
  }

  function isTvScheduleVideo(item) {
    if (isTVShowItem(item)) return true;
    return isBroadcastHistoryChannel(item);
  }

  function titleMatchKey(title) {
    return normalizeTitle(title).toLowerCase();
  }

  function parseScheduleEntry(entry) {
    var m = entry.match(/^(.*?):\s*(.*)$/);
    if (!m) return { displayDate: entry, title: entry };
    return { displayDate: m[1].trim(), title: m[2].trim() };
  }

  function getDateKey(displayDateStr) {
    var match = displayDateStr.match(/([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})/);
    if (!match) return null;
    var month = match[1];
    var day = parseInt(match[2], 10);
    var year = parseInt(match[3], 10);
    var d = new Date(month + " " + day + ", " + year);
    if (isNaN(d.getTime())) return null;
    return dateFmt.format(d);
  }

  function pad2(n) {
    return n < 10 ? "0" + n : String(n);
  }

  /** Schedule display date → YYYYMMDD for {base}/{date}.jpg */
  function getDateYyyymmdd(displayDateStr) {
    var match = String(displayDateStr || "").match(
      /([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})/
    );
    if (!match) return null;
    var d = new Date(match[1] + " " + match[2] + ", " + match[3]);
    if (isNaN(d.getTime())) return null;
    return d.getFullYear() + pad2(d.getMonth() + 1) + pad2(d.getDate());
  }

  function ensureTrailingSlash(base) {
    var b = String(base || "").trim();
    if (!b) return "";
    if (b.charAt(b.length - 1) !== "/") b += "/";
    return b;
  }

  /**
   * Ordered list of URL bases for thumb-only cards.
   * data-thumb-base → single override; data-thumb-bases → comma-separated list;
   * else DEFAULT_THUMB_BASES (GitHub tv-thumbs, then CMS Userfiles).
   */
  function thumbBases(container) {
    var single = (
      (container && container.getAttribute("data-thumb-base")) ||
      ""
    ).trim();
    if (single) {
      return [ensureTrailingSlash(single)];
    }
    var multi = (
      (container && container.getAttribute("data-thumb-bases")) ||
      ""
    ).trim();
    if (multi) {
      return multi
        .split(",")
        .map(function (s) {
          return ensureTrailingSlash(s);
        })
        .filter(Boolean);
    }
    return DEFAULT_THUMB_BASES.map(ensureTrailingSlash);
  }

  function thumbUrlForDate(base, displayDateStr) {
    var ymd = getDateYyyymmdd(displayDateStr);
    if (!ymd || !base) return "";
    return ensureTrailingSlash(base) + ymd + ".jpg";
  }

  /** Candidate URLs for a schedule date (one per base). */
  function thumbUrlsForDate(bases, displayDateStr) {
    var ymd = getDateYyyymmdd(displayDateStr);
    if (!ymd) return [];
    return (bases || [])
      .map(function (base) {
        return thumbUrlForDate(base, displayDateStr);
      })
      .filter(Boolean);
  }

  function probeImage(url) {
    return new Promise(function (resolve) {
      if (!url) {
        resolve(false);
        return;
      }
      var img = new Image();
      img.onload = function () {
        resolve(true);
      };
      img.onerror = function () {
        resolve(false);
      };
      img.src = url;
    });
  }

  /** First URL in the list that loads as an image, or null. */
  function probeFirstImage(urls) {
    var list = urls || [];
    var i = 0;
    function next() {
      if (i >= list.length) return Promise.resolve(null);
      var url = list[i++];
      return probeImage(url).then(function (ok) {
        if (ok) return url;
        return next();
      });
    }
    return next();
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

  function attachCardClicks(root) {
    root = root || document.getElementById("content") || document;
    root.querySelectorAll(".rw-card[data-video-id]").forEach(function (card) {
      var videoId = card.getAttribute("data-video-id");
      if (!videoId) return;
      var thumbWrap = card.querySelector(".rw-thumbWrap");
      var titleWrap = card.querySelector(".rw-title");
      var openPlayer = function (e) {
        if (e && (e.metaKey || e.ctrlKey || e.shiftKey)) {
          var lnk = card.getAttribute("data-link");
          if (lnk) window.open(lnk, "_blank");
          return;
        }
        if (e) e.preventDefault();
        showRumbleOverlay(videoId);
      };
      if (thumbWrap) thumbWrap.style.cursor = "pointer";
      if (titleWrap) titleWrap.style.cursor = "pointer";
      if (thumbWrap) thumbWrap.addEventListener("click", openPlayer);
      if (titleWrap) titleWrap.addEventListener("click", openPlayer);
      card.style.cursor = "pointer";
      card.addEventListener("click", function (e) {
        if (e.target.closest(".rw-thumbWrap") || e.target.closest(".rw-title")) {
          return;
        }
        openPlayer(e);
      });
    });
  }

  function renderCardHtml(opts) {
    var title = opts.title || "";
    var date = opts.date || "";
    var thumb = opts.thumb || "";
    var videoId = opts.videoId || "";
    var link = opts.link || "";
    var shortClass = opts.shortClass || "";
    var staticOnly = !!opts.staticOnly;
    var thumbStyle = thumb
      ? ' style="--rw-thumb-bg: url(\'' + escapeHtml(thumb) + "')\""
      : "";
    var cardClass =
      "rw-card" + shortClass + (staticOnly ? " rw-card--static" : "");
    var dataAttrs = staticOnly
      ? ""
      : ' data-video-id="' +
        escapeHtml(videoId) +
        '" data-link="' +
        escapeHtml(link) +
        '"';

    return (
      '<div class="' +
      cardClass +
      '"' +
      dataAttrs +
      ">" +
      '<div class="rw-thumbWrap"' +
      thumbStyle +
      ">" +
      (thumb
        ? '<img class="rw-thumb" src="' + escapeHtml(thumb) + '" alt="">'
        : "") +
      "</div>" +
      '<div class="rw-meta">' +
      '<div class="rw-title">' +
      escapeHtml(title) +
      "</div>" +
      '<div class="rw-date">' +
      escapeHtml(date) +
      "</div>" +
      "</div>" +
      "</div>"
    );
  }

  function renderVideoCard(video, scheduleDisplayDate, scheduleTitle) {
    var fromSchedule = scheduleTitle && String(scheduleTitle).trim();
    var title =
      fromSchedule ||
      normalizeTitle(video && video.title) ||
      scheduleDisplayDate;
    return renderCardHtml({
      title: title,
      date: scheduleDisplayDate || getTVAirDateStr(video),
      thumb: getThumb(video),
      videoId: getVideoId(video),
      link: getLink(video),
      shortClass: isShort(video) ? " rw-card--short" : "",
      staticOnly: false,
    });
  }

  /** Non-clickable card when only a site thumb exists (no Rumble video). */
  function renderThumbOnlyCard(scheduleDisplayDate, scheduleTitle, thumbUrl) {
    var title =
      (scheduleTitle && String(scheduleTitle).trim()) || scheduleDisplayDate;
    return renderCardHtml({
      title: title,
      date: scheduleDisplayDate,
      thumb: thumbUrl,
      staticOnly: true,
    });
  }

  function feedUrl(container) {
    return (
      (container.getAttribute("data-feed") || "").trim() || DEFAULT_FEED
    );
  }

  function scheduleUrl(container) {
    return (
      (container.getAttribute("data-schedule") || "").trim() ||
      DEFAULT_SCHEDULE
    );
  }

  function loadAndRenderSchedule() {
    var container = document.getElementById("content");
    if (!container) {
      console.warn("Warning-TV-Broadcasts: #content not found; skip.");
      return;
    }

    var ul = container.querySelector("ul");
    if (!ul) {
      ul = document.createElement("ul");
      container.appendChild(ul);
    }
    ul.innerHTML = "";

    var videoByDateKey = new Map();
    var videoByTitleKey = new Map();
    var schedule = [];
    var feed = feedUrl(container);
    var sched = scheduleUrl(container);

    Promise.allSettled([
      fetch(feed, { cache: "no-store" }),
      fetch(sched, { cache: "no-store" }),
    ])
      .then(function (results) {
        var feedRes = results[0];
        var schedRes = results[1];

        var feedChain = Promise.resolve();
        if (feedRes.status === "fulfilled" && feedRes.value.ok) {
          feedChain = feedRes.value.json().then(function (data) {
            var items =
              data && Array.isArray(data.items) ? data.items : [];
            items = items.filter(isTvScheduleVideo);
            items.forEach(function (item) {
              if (isTVShowItem(item)) {
                var key = getTVAirDateStr(item);
                if (key) videoByDateKey.set(key, item);
              } else if (isBroadcastHistoryChannel(item)) {
                var tKey = titleMatchKey(item.title);
                if (tKey) videoByTitleKey.set(tKey, item);
              }
            });
          });
        } else if (feedRes.status === "rejected") {
          console.warn("Could not load video feed:", feedRes.reason);
        }

        var schedChain = Promise.resolve();
        if (schedRes.status === "fulfilled" && schedRes.value.ok) {
          schedChain = schedRes.value.text().then(function (txt) {
            schedule = txt
              .split(/\r?\n/)
              .map(function (l) {
                return l.trim();
              })
              .filter(Boolean);
          });
        } else if (schedRes.status === "rejected") {
          console.warn("Could not load TV schedule:", schedRes.reason);
        }

        return Promise.all([feedChain, schedChain]);
      })
      .then(function () {
        var bases = thumbBases(container);

        var rows = schedule.map(function (entry) {
          var parsed = parseScheduleEntry(entry);
          var key = getDateKey(parsed.displayDate);
          var video = key ? videoByDateKey.get(key) : null;
          if (!video) {
            var tKey = titleMatchKey(parsed.title);
            if (tKey) video = videoByTitleKey.get(tKey) || null;
          }
          var thumbCandidates = video
            ? []
            : thumbUrlsForDate(bases, parsed.displayDate);
          return {
            entry: entry,
            parsed: parsed,
            video: video,
            thumbUrl: "",
            thumbOk: false,
            thumbCandidates: thumbCandidates,
          };
        });

        return Promise.all(
          rows.map(function (row) {
            if (row.video || !row.thumbCandidates.length) {
              return Promise.resolve(row);
            }
            return probeFirstImage(row.thumbCandidates).then(function (url) {
              if (url) {
                row.thumbUrl = url;
                row.thumbOk = true;
              }
              return row;
            });
          })
        );
      })
      .then(function (rows) {
        if (!rows) return;

        var dateRegex =
          /^(?:[A-Za-z]+,\s)?([A-Za-z]+)\s(\d{1,2}),\s(\d{4})/;
        var today = new Date();
        var closestLi = null;
        var minDiff = Infinity;

        rows.forEach(function (row) {
          var parsed = row.parsed;
          var entry = row.entry;
          var li = document.createElement("li");

          if (row.video) {
            li.classList.add("has-video");
            li.dataset.date = parsed.displayDate;
            li.innerHTML = renderVideoCard(
              row.video,
              parsed.displayDate,
              parsed.title
            );
          } else if (row.thumbOk && row.thumbUrl) {
            li.classList.add("has-thumb");
            li.dataset.date = parsed.displayDate;
            li.innerHTML = renderThumbOnlyCard(
              parsed.displayDate,
              parsed.title,
              row.thumbUrl
            );
          } else {
            li.textContent = entry;
            var match = entry.match(dateRegex);
            if (match) {
              li.dataset.date =
                match[1] + " " + match[2] + ", " + match[3];
            }
          }

          ul.appendChild(li);

          var dateStr = li.dataset.date || li.textContent;
          var m2 = dateStr.match(dateRegex);
          if (m2) {
            var month = m2[1];
            var day = parseInt(m2[2], 10);
            var year = parseInt(m2[3], 10);
            var liDate = new Date(month + " " + day + ", " + year);
            var diff = liDate - today;
            if (diff >= 0 && diff < minDiff) {
              minDiff = diff;
              closestLi = li;
            }
          }
        });

        if (closestLi) {
          closestLi.classList.add("highlight");
        }

        // Only cards with data-video-id get click handlers
        attachCardClicks(container);
      })
      .catch(function (e) {
        console.warn("Error loading feed or schedule:", e);
      });
  }

  function init() {
    ensureRumbleEmbedScript();
    wireRumbleModalHandlers();
    loadAndRenderSchedule();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
