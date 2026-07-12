/**
 * Shortwave Broadcasts — schedule list with paging.
 * Loaded from CMS via:
 *   <script src="https://jhansenwmi.github.io/rumble-WMI-videos/widgets/Shortwave-Broadcasts.js"></script>
 *
 * Mount (in CMS shell):
 *   <div id="content"
 *        data-schedule="https://jhansenwmi.github.io/rumble-WMI-videos/shortwave-schedule.txt">
 *     …chrome…
 *     <ul id="schedule-list"></ul>
 *   </div>
 *
 * Data: docs/shortwave-schedule.txt — "Fri, Jul 3, 2026: Title" per line.
 */
(function () {
  var DEFAULT_SCHEDULE =
    "https://jhansenwmi.github.io/rumble-WMI-videos/shortwave-schedule.txt";
  var PAGE_SIZE = 50;

  var allShortwaveLines = [];
  var currentShortwavePage = 0;
  var shortwaveUl = null;
  var isFirstRender = true;

  function scheduleUrl(container) {
    return (
      (container && container.getAttribute("data-schedule")) || ""
    ).trim() || DEFAULT_SCHEDULE;
  }

  function highlightUpcoming(ul) {
    var today = new Date();
    today.setHours(0, 0, 0, 0);

    var dateRegex = /^(?:[A-Za-z]+,\s)?([A-Za-z]+)\s(\d{1,2}),\s(\d{4})/;
    var closestLi = null;
    var minDiff = Infinity;

    var listItems = ul
      ? ul.querySelectorAll("li")
      : document.querySelectorAll("#content ul li");

    listItems.forEach(function (li) {
      var text = li.textContent || "";
      var match = text.match(dateRegex);
      if (match) {
        var month = match[1];
        var day = parseInt(match[2], 10);
        var year = parseInt(match[3], 10);
        var liDate = new Date(
          year,
          new Date(month + " 1, " + year).getMonth(),
          day
        );
        liDate.setHours(0, 0, 0, 0);
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
  }

  function getJQ() {
    if (typeof jQ !== "undefined") return jQ;
    if (typeof jQuery !== "undefined") return jQuery;
    return null;
  }

  function updatePagerUI() {
    var totalPages = Math.ceil(allShortwaveLines.length / PAGE_SIZE) || 1;
    var start = currentShortwavePage * PAGE_SIZE + 1;
    var end = Math.min(
      (currentShortwavePage + 1) * PAGE_SIZE,
      allShortwaveLines.length
    );
    var info =
      "Page " +
      (currentShortwavePage + 1) +
      " of " +
      totalPages +
      " &nbsp;(" +
      start +
      "–" +
      end +
      " of " +
      allShortwaveLines.length +
      ")";

    var j = getJQ();
    if (j) {
      j("#shortwave-page-info").html(info);
      j("#shortwave-prev").toggle(currentShortwavePage > 0);
      j("#shortwave-next").toggle(currentShortwavePage < totalPages - 1);
      return;
    }

    var infoEl = document.getElementById("shortwave-page-info");
    if (infoEl) infoEl.innerHTML = info;
    var prev = document.getElementById("shortwave-prev");
    var next = document.getElementById("shortwave-next");
    if (prev)
      prev.style.display = currentShortwavePage > 0 ? "" : "none";
    if (next)
      next.style.display =
        currentShortwavePage < totalPages - 1 ? "" : "none";
  }

  function renderShortwavePage(page) {
    if (!shortwaveUl || !allShortwaveLines.length) return;

    var totalPages = Math.ceil(allShortwaveLines.length / PAGE_SIZE) || 1;
    currentShortwavePage = Math.max(
      0,
      Math.min(page, totalPages - 1)
    );
    var isLastPage = currentShortwavePage === totalPages - 1;

    var wasFirstRender = isFirstRender;
    if (isFirstRender) {
      isFirstRender = false;
    }

    var pagerEl = document.getElementById("shortwave-pager");
    var rectBefore =
      !wasFirstRender && pagerEl ? pagerEl.getBoundingClientRect() : null;

    if (isLastPage) {
      shortwaveUl.classList.add("last-page");
    } else {
      shortwaveUl.classList.remove("last-page");
    }

    var start = currentShortwavePage * PAGE_SIZE;
    var end = Math.min(start + PAGE_SIZE, allShortwaveLines.length);
    var pageLines = allShortwaveLines.slice(start, end);

    shortwaveUl.innerHTML = "";
    pageLines.forEach(function (line) {
      var li = document.createElement("li");
      li.textContent = line;
      shortwaveUl.appendChild(li);
    });

    updatePagerUI();
    highlightUpcoming(shortwaveUl);

    if (pagerEl && !wasFirstRender && rectBefore) {
      var settleFrames = isLastPage ? 2 : 1;
      var step = function (remaining) {
        if (remaining > 1) {
          requestAnimationFrame(function () {
            step(remaining - 1);
          });
          return;
        }
        requestAnimationFrame(function () {
          var rectAfter = pagerEl.getBoundingClientRect();
          var delta = rectAfter.top - rectBefore.top;
          if (delta !== 0) {
            window.scrollBy(0, delta);
          }
        });
      };
      step(settleFrames);
    }
  }

  function setupShortwavePager(ul) {
    shortwaveUl = ul;
    var container = ul.parentNode || document.getElementById("content");
    var pager = document.getElementById("shortwave-pager");
    if (!pager) {
      pager = document.createElement("div");
      pager.id = "shortwave-pager";
      pager.innerHTML =
        '<button type="button" id="shortwave-prev">« Newer 50</button>' +
        '<span id="shortwave-page-info" style="margin: 0 10px; font-size: 0.9em;"></span>' +
        '<button type="button" id="shortwave-next">Older 50 »</button>';
      if (ul.nextSibling) {
        container.insertBefore(pager, ul.nextSibling);
      } else {
        container.appendChild(pager);
      }
    }

    var j = getJQ();
    if (!j) {
      var prev = document.getElementById("shortwave-prev");
      var next = document.getElementById("shortwave-next");
      if (prev)
        prev.onclick = function () {
          renderShortwavePage(currentShortwavePage - 1);
        };
      if (next)
        next.onclick = function () {
          renderShortwavePage(currentShortwavePage + 1);
        };
      return;
    }

    j("#shortwave-prev")
      .off("click")
      .on("click", function () {
        renderShortwavePage(currentShortwavePage - 1);
      });
    j("#shortwave-next")
      .off("click")
      .on("click", function () {
        renderShortwavePage(currentShortwavePage + 1);
      });
  }

  function loadShortwaveSchedule() {
    var container =
      document.getElementById("content") ||
      document.querySelector("#content");
    if (!container) {
      console.warn("Shortwave-Broadcasts: #content not found; skip.");
      return;
    }

    var ul =
      container.querySelector("#schedule-list") ||
      container.querySelector("ul");
    if (!ul) {
      ul = document.createElement("ul");
      ul.id = "schedule-list";
      var p = container.querySelector("p");
      if (p && p.nextSibling) {
        container.insertBefore(ul, p.nextSibling);
      } else {
        container.appendChild(ul);
      }
    }
    ul.innerHTML = "";

    var url = scheduleUrl(container);
    fetch(url, { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.text();
      })
      .then(function (txt) {
        allShortwaveLines = txt
          .split(/\r?\n/)
          .map(function (l) {
            return l.trim();
          })
          .filter(Boolean);

        if (allShortwaveLines.length === 0) {
          var li = document.createElement("li");
          li.textContent = "Unable to load schedule.";
          ul.appendChild(li);
          return;
        }

        setupShortwavePager(ul);
        currentShortwavePage = 0;
        renderShortwavePage(currentShortwavePage);
      })
      .catch(function (e) {
        console.warn("Could not load shortwave-schedule.txt:", e);
        var li = document.createElement("li");
        li.textContent = "Unable to load schedule.";
        ul.appendChild(li);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadShortwaveSchedule);
  } else {
    loadShortwaveSchedule();
  }
})();
