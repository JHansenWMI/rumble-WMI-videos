/**
 * Dorcas Fund galleries.
 * CMS mount:
 *   <div id="dorcasFundGalleries"
 *        data-dorcas-galleries="https://jhansenwmi.github.io/rumble-WMI-videos/dorcas-fund-galleries.html?v=VERSION"></div>
 *   <script src="https://jhansenwmi.github.io/rumble-WMI-videos/widgets/Dorcas-Fund-Galleries.js?v=VERSION"></script>
 *
 * The fragment (intro, gallery headings, slides) lives in
 * docs/dorcas-fund-galleries.html. Photo updates do not need another CMS paste.
 */
(function () {
  var GALLERIES_VERSION = "20261012a";
  var PAGES = "https://jhansenwmi.github.io/rumble-WMI-videos/";
  var DEFAULT_HTML = PAGES + "dorcas-fund-galleries.html?v=" + GALLERIES_VERSION;
  var CSS_ID = "wmi-dorcas-fund-galleries-css";

  function currentScriptSrc() {
    if (document.currentScript && document.currentScript.src) {
      return document.currentScript.src;
    }
    var scripts = document.getElementsByTagName("script");
    for (var i = scripts.length - 1; i >= 0; i--) {
      var src = scripts[i].src || "";
      if (src.indexOf("Dorcas-Fund-Galleries.js") >= 0) return src;
    }
    return "";
  }

  function ensureStylesheet() {
    if (document.getElementById(CSS_ID)) return;
    var src = currentScriptSrc();
    var href = src
      ? src.replace(/Dorcas-Fund-Galleries\.js(\?.*)?$/, "Dorcas-Fund-Galleries.css?v=" + GALLERIES_VERSION)
      : PAGES + "widgets/Dorcas-Fund-Galleries.css?v=" + GALLERIES_VERSION;
    var link = document.createElement("link");
    link.id = CSS_ID;
    link.rel = "stylesheet";
    link.href = href;
    (document.head || document.documentElement).appendChild(link);
  }

  function findMount() {
    return (
      document.getElementById("dorcasFundGalleries") ||
      document.querySelector("[data-dorcas-galleries]")
    );
  }

  function htmlUrl(mount) {
    return (mount.getAttribute("data-dorcas-galleries") || "").trim() || DEFAULT_HTML;
  }

  function loadSwiper(done) {
    if (window.Swiper) {
      done();
      return;
    }
    var link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://cdn.jsdelivr.net/npm/swiper@11/swiper-bundle.min.css";
    document.head.appendChild(link);

    var script = document.createElement("script");
    script.src = "https://cdn.jsdelivr.net/npm/swiper@11/swiper-bundle.min.js";
    script.onload = done;
    script.onerror = function () {
      console.error("Dorcas galleries: Swiper failed to load");
    };
    document.head.appendChild(script);
  }

  function initCarousels(root) {
    var swipers = {};
    var nodes = root.querySelectorAll(".swiper[id]");
    var config = [];
    for (var i = 0; i < nodes.length; i++) {
      config.push({ id: nodes[i].id });
    }

    var knownTotals = {
      "carousel-1": 113,
      "carousel-2": 9,
      "carousel-3": 96,
      "carousel-4": 133
    };

    config.forEach(function (item) {
      var id = item.id;
      var container = root.querySelector("#" + id);
      if (!container) return;

      var playBtn = document.createElement("button");
      playBtn.type = "button";
      playBtn.tabIndex = -1;
      playBtn.innerHTML = "Play";
      playBtn.style.cssText = [
        "position:absolute",
        "bottom:15%",
        "left:50%",
        "transform:translateX(-50%)",
        "z-index:10",
        "border:none",
        "padding:12px 20px",
        "border-radius:30px",
        "cursor:pointer",
        "font-size:16px",
        "font-weight:bold",
        "box-shadow:0 4px 12px rgba(0,0,0,0.3)",
        "transition:all 0.3s ease"
      ].join(";");
      container.appendChild(playBtn);

      swipers[id] = {
        playBtn: playBtn,
        container: container,
        swiper: null,
        hasStarted: false
      };
    });

    function slideTotal(id, container) {
      var wrapper = container.querySelector(".swiper-wrapper");
      var count = wrapper
        ? wrapper.querySelectorAll(":scope > .swiper-slide").length
        : 0;
      var marked = parseInt(container.getAttribute("data-count") || "", 10);
      if (marked > 0) return marked;
      if (count === 0 && knownTotals[id]) return knownTotals[id];
      return count;
    }

    function createSwiper(id) {
      var s = swipers[id];
      if (!s || s.swiper) return;

      var container = s.container;
      var slideCount = slideTotal(id, container);

      try {
        var swiper = new Swiper("#" + id, {
          effect: "slide",
          grabCursor: true,
          centeredSlides: true,
          slidesPerView: 1,
          spaceBetween: 0,
          loop: false,
          virtual: true,
          lazy: true,
          watchOverflow: true,
          observer: true,
          observeParents: true,
          observeSlideChildren: true,
          touchEventsTarget: "container",
          simulateTouch: true,
          passiveListeners: true,
          preventClicks: false,
          touchStartPreventDefault: false,
          autoplay: {
            delay: 2600,
            disableOnInteraction: false,
            pauseOnMouseEnter: true
          },
          navigation: {
            nextEl: "#" + id + " .swiper-button-next",
            prevEl: "#" + id + " .swiper-button-prev"
          }
        });

        s.swiper = swiper;
        swiper.on("autoplayStop", function () {
          if (s.playBtn) s.playBtn.innerHTML = "Play";
        });

        var counterEl = document.createElement("div");
        counterEl.className = "slide-counter";
        container.appendChild(counterEl);

        var updateCounter = function () {
          var current = (swiper.realIndex || swiper.activeIndex || 0) + 1;
          counterEl.textContent = current + " of " + slideCount;
        };
        swiper.on("init", updateCounter);
        swiper.on("slideChange", updateCounter);
        setTimeout(updateCounter, 60);

        s.counterEl = counterEl;
        s.totalSlides = slideCount;
      } catch (error) {
        console.error("Failed to create " + id, error);
      }
    }

    function stopAllExcept(currentId) {
      config.forEach(function (item) {
        if (item.id === currentId) return;
        var other = swipers[item.id];
        if (other && other.swiper && other.swiper.autoplay && other.swiper.autoplay.running) {
          other.swiper.autoplay.stop();
          if (other.playBtn) other.playBtn.innerHTML = "Play";
        }
      });
    }

    config.forEach(function (item) {
      var s = swipers[item.id];
      if (!s || !s.playBtn) return;
      s.playBtn.onclick = function (e) {
        e.preventDefault();
        e.stopPropagation();
        var swiper = s.swiper;
        if (swiper && swiper.autoplay && swiper.autoplay.running) {
          swiper.autoplay.stop();
          s.playBtn.innerHTML = "Play";
          return;
        }
        stopAllExcept(item.id);
        if (!swiper) createSwiper(item.id);
        var active = swipers[item.id].swiper;
        if (!active) return;
        if (!s.hasStarted) {
          setTimeout(function () {
            active.slideNext();
            s.hasStarted = true;
            if (active.autoplay) active.autoplay.start();
          }, 350);
        } else if (active.autoplay) {
          active.autoplay.start();
        }
        s.playBtn.innerHTML = "Pause";
      };
    });

    if (!("IntersectionObserver" in window)) {
      config.forEach(function (item) { createSwiper(item.id); });
      return;
    }

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var id = entry.target.id;
        if (swipers[id] && !swipers[id].swiper) createSwiper(id);
      });
    }, { rootMargin: "200px 0px", threshold: 0.1 });

    config.forEach(function (item) {
      var container = root.querySelector("#" + item.id);
      if (container) observer.observe(container);
    });
  }

  function showError(mount, message) {
    mount.innerHTML = '<p style="color:#502785">' + message + "</p>";
  }

  var mount = findMount();
  if (!mount) return;
  ensureStylesheet();

  fetch(htmlUrl(mount), { credentials: "omit" })
    .then(function (response) {
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.text();
    })
    .then(function (html) {
      mount.innerHTML = html;
      loadSwiper(function () { initCarousels(mount); });
    })
    .catch(function (error) {
      console.error("Dorcas galleries failed to load", error);
      showError(mount, "The photo galleries could not be loaded. Please refresh the page.");
    });
})();
