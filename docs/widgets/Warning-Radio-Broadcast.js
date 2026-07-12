/**
 * Warning Radio Broadcast — radio schedule list with paging.
 * Loaded from CMS via:
 *   <script src="https://jhansenwmi.github.io/rumble-WMI-videos/widgets/Warning-Radio-Broadcast.js"></script>
 *
 * Mount (in CMS shell):
 *   <div id="content"
 *        data-schedule="https://jhansenwmi.github.io/rumble-WMI-videos/radio-schedule.txt">
 *     …chrome…
 *     <ul id="schedule-list"></ul>
 *   </div>
 *
 * Data: docs/radio-schedule.txt — "Fri, Jul 3, 2026: Title" per line.
 */
(function () {
  var DEFAULT_SCHEDULE =
    "https://jhansenwmi.github.io/rumble-WMI-videos/radio-schedule.txt";
  var PAGE_SIZE = 50;

  var allRadioLines = [];
  var currentRadioPage = 0;
  var radioUl = null;
  var isFirstRender = true;

  function scheduleUrl(container) {
    return (
      (container && container.getAttribute("data-schedule")) || ""
    ).trim() || DEFAULT_SCHEDULE;
  }

  function decodeHtmlEntities(str) {
    var el = document.createElement("textarea");
    el.innerHTML = str;
    return el.value;
  }

  function getPacificOffset(date) {
    var pacificString = date.toLocaleString("en-US", {
      timeZone: "America/Los_Angeles",
      year: "numeric",
      month: "numeric",
      day: "numeric",
      hour: "numeric",
      minute: "numeric",
      second: "numeric",
      hour12: false,
    });
    var parts = pacificString.split(", ");
    var datePart = parts[0];
    var timePart = parts[1];
    var dParts = datePart.split("/").map(Number);
    var tParts = timePart.split(":").map(Number);
    var month = dParts[0];
    var day = dParts[1];
    var year = dParts[2];
    var hour = tParts[0];
    var minute = tParts[1];
    var second = tParts[2];
    var pacificDate = new Date(year, month - 1, day, hour, minute, second);
    var utcDate = new Date(
      Date.UTC(
        date.getUTCFullYear(),
        date.getUTCMonth(),
        date.getUTCDate(),
        date.getUTCHours(),
        date.getUTCMinutes(),
        date.getUTCSeconds()
      )
    );
    return (pacificDate - utcDate) / (1000 * 60);
  }

  function highlightUpcoming(ul) {
    var now = new Date();
    var pacificOffsetMinutes = getPacificOffset(now);
    var userOffsetMinutes = now.getTimezoneOffset();
    var offsetDiffHours = (userOffsetMinutes - pacificOffsetMinutes) / 60;
    var nowPacific = new Date(
      now.getTime() + offsetDiffHours * 60 * 60 * 1000
    );
    var todayMidnight = new Date(
      nowPacific.getFullYear(),
      nowPacific.getMonth(),
      nowPacific.getDate()
    );

    var broadcastHourPT = 12;
    var broadcastMinute = 30;
    var broadcastTime = new Date(
      nowPacific.getFullYear(),
      nowPacific.getMonth(),
      nowPacific.getDate(),
      broadcastHourPT,
      broadcastMinute
    );
    var targetDate =
      nowPacific < broadcastTime
        ? todayMidnight
        : new Date(todayMidnight.getTime() + 24 * 60 * 60 * 1000);

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
        var diff = liDate - targetDate;
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
    var totalPages = Math.ceil(allRadioLines.length / PAGE_SIZE) || 1;
    var start = currentRadioPage * PAGE_SIZE + 1;
    var end = Math.min(
      (currentRadioPage + 1) * PAGE_SIZE,
      allRadioLines.length
    );
    var info =
      "Page " +
      (currentRadioPage + 1) +
      " of " +
      totalPages +
      " &nbsp;(" +
      start +
      "–" +
      end +
      " of " +
      allRadioLines.length +
      ")";

    var j = getJQ();
    if (j) {
      j("#radio-page-info").html(info);
      j("#radio-prev").toggle(currentRadioPage > 0);
      j("#radio-next").toggle(currentRadioPage < totalPages - 1);
      return;
    }

    var infoEl = document.getElementById("radio-page-info");
    if (infoEl) infoEl.innerHTML = info;
    var prev = document.getElementById("radio-prev");
    var next = document.getElementById("radio-next");
    if (prev) prev.style.display = currentRadioPage > 0 ? "" : "none";
    if (next)
      next.style.display =
        currentRadioPage < totalPages - 1 ? "" : "none";
  }

  function renderRadioPage(page) {
    if (!radioUl || !allRadioLines.length) return;

    var totalPages = Math.ceil(allRadioLines.length / PAGE_SIZE) || 1;
    currentRadioPage = Math.max(0, Math.min(page, totalPages - 1));
    var isLastPage = currentRadioPage === totalPages - 1;

    var wasFirstRender = isFirstRender;
    if (isFirstRender) {
      isFirstRender = false;
    }

    var pagerEl = document.getElementById("radio-pager");
    var rectBefore =
      !wasFirstRender && pagerEl ? pagerEl.getBoundingClientRect() : null;

    if (isLastPage) {
      radioUl.classList.add("last-page");
    } else {
      radioUl.classList.remove("last-page");
    }

    var start = currentRadioPage * PAGE_SIZE;
    var end = Math.min(start + PAGE_SIZE, allRadioLines.length);
    var pageLines = allRadioLines.slice(start, end);

    radioUl.innerHTML = "";
    pageLines.forEach(function (line) {
      var li = document.createElement("li");
      li.textContent = decodeHtmlEntities(line);
      radioUl.appendChild(li);
    });

    updatePagerUI();
    highlightUpcoming(radioUl);

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

  function setupRadioPager(ul) {
    radioUl = ul;
    var container = ul.parentNode || document.getElementById("content");
    var pager = document.getElementById("radio-pager");
    if (!pager) {
      pager = document.createElement("div");
      pager.id = "radio-pager";
      pager.innerHTML =
        '<button type="button" id="radio-prev">« Newer 50</button>' +
        '<span id="radio-page-info" style="margin: 0 10px; font-size: 0.9em;"></span>' +
        '<button type="button" id="radio-next">Older 50 »</button>';
      if (ul.nextSibling) {
        container.insertBefore(pager, ul.nextSibling);
      } else {
        container.appendChild(pager);
      }
    }

    var j = getJQ();
    if (!j) {
      var prev = document.getElementById("radio-prev");
      var next = document.getElementById("radio-next");
      if (prev)
        prev.onclick = function () {
          renderRadioPage(currentRadioPage - 1);
        };
      if (next)
        next.onclick = function () {
          renderRadioPage(currentRadioPage + 1);
        };
      return;
    }

    j("#radio-prev")
      .off("click")
      .on("click", function () {
        renderRadioPage(currentRadioPage - 1);
      });
    j("#radio-next")
      .off("click")
      .on("click", function () {
        renderRadioPage(currentRadioPage + 1);
      });
  }

  function loadRadioSchedule() {
    var container =
      document.getElementById("content") ||
      document.querySelector("#content");
    if (!container) {
      console.warn("Warning-Radio-Broadcast: #content not found; skip.");
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
        allRadioLines = txt
          .split(/\r?\n/)
          .map(function (l) {
            return l.trim();
          })
          .filter(Boolean);

        if (allRadioLines.length === 0) {
          var li = document.createElement("li");
          li.textContent = "Unable to load schedule.";
          ul.appendChild(li);
          return;
        }

        setupRadioPager(ul);
        currentRadioPage = 0;
        renderRadioPage(currentRadioPage);
      })
      .catch(function (e) {
        console.warn("Could not load radio-schedule.txt:", e);
        var li = document.createElement("li");
        li.textContent = "Unable to load schedule.";
        ul.appendChild(li);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadRadioSchedule);
  } else {
    loadRadioSchedule();
  }
})();
