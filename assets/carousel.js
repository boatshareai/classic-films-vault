/* Featured-titles carousel: arrow buttons over a native scroll-snap track.
   No autoplay — the track is a plain scroller, so touch swipe and keyboard
   both work even if this script never runs. */
(function () {
  "use strict";

  var root = document.querySelector("[data-carousel]");
  if (!root) return;

  var track = root.querySelector(".carousel-track");
  var prev = root.querySelector(".carousel-btn.prev");
  var next = root.querySelector(".carousel-btn.next");
  if (!track || !prev || !next) return;

  function page() {
    // scroll by a near-viewport step so cards don't get half-skipped
    return Math.max(track.clientWidth * 0.8, 160);
  }

  // Scroll snapping and sub-pixel rounding mean scrollLeft rarely settles
  // exactly on 0 or on the maximum, so the bounds need a tolerance. Anything
  // well under one scroll step is safe.
  var EPS = 8;

  function sync() {
    var max = track.scrollWidth - track.clientWidth;
    prev.disabled = track.scrollLeft <= EPS;
    next.disabled = track.scrollLeft >= max - EPS;
  }

  prev.addEventListener("click", function () {
    track.scrollBy({ left: -page(), behavior: "smooth" });
  });
  next.addEventListener("click", function () {
    track.scrollBy({ left: page(), behavior: "smooth" });
  });

  track.addEventListener("scroll", function () {
    window.requestAnimationFrame(sync);
  });
  window.addEventListener("resize", sync);

  sync();
})();
