/* Catalog browse: search, filter, sort. Data is inlined in the page, so
   filtering is instant and there is no fetch to wait on. */
(function () {
  "use strict";

  var films = JSON.parse(document.getElementById("catalog-data").textContent);
  var tbody = document.getElementById("rows");
  var empty = document.getElementById("empty");
  var count = document.getElementById("count");

  var q = document.getElementById("q");
  var genre = document.getElementById("genre");
  var decade = document.getElementById("decade");
  var lang = document.getElementById("lang");
  var runtime = document.getElementById("runtime");
  var status = document.getElementById("status");

  var sortKey = "t";
  var sortDir = 1;

  // Deep links from the home page and film pages: ?genre=Western, ?decade=1940s,
  // ?intl=1, ?q=holmes
  (function applyQuery() {
    var p = new URLSearchParams(location.search);
    if (p.get("q")) q.value = p.get("q");
    if (p.get("genre")) genre.value = p.get("genre");
    if (p.get("decade")) decade.value = p.get("decade");
    if (p.get("status")) status.value = p.get("status");
    if (p.get("intl")) lang.dataset.intl = "1";
  })();

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function matches(f) {
    var term = q.value.trim().toLowerCase();
    if (term) {
      var hay = (f.t + " " + f.o + " " + f.g.join(" ") + " " + f.y).toLowerCase();
      // every whitespace-separated word must appear somewhere
      var words = term.split(/\s+/);
      for (var i = 0; i < words.length; i++) {
        if (hay.indexOf(words[i]) === -1) return false;
      }
    }
    if (genre.value && f.g.indexOf(genre.value) === -1) return false;
    if (decade.value && f.d !== decade.value) return false;

    if (lang.dataset.intl === "1") {
      if (!f.l || f.l === "English") return false;
    } else if (lang.value === "__none") {
      if (f.l) return false;
    } else if (lang.value && f.l !== lang.value) {
      return false;
    }

    if (runtime.value === "__none") {
      if (f.r) return false;
    } else if (runtime.value) {
      if (!f.r) return false;
      var b = runtime.value.split("-");
      if (f.r < +b[0] || f.r > +b[1]) return false;
    }

    if (status.value && f.st !== status.value) return false;
    return true;
  }

  function compare(a, b) {
    var x = a[sortKey];
    var y = b[sortKey];
    // Titles sort as text; year and runtime as numbers, with blanks last.
    if (sortKey === "t") {
      return x.toLowerCase().localeCompare(y.toLowerCase()) * sortDir;
    }
    var nx = x === null || x === "" ? null : +x;
    var ny = y === null || y === "" ? null : +y;
    if (nx === null && ny === null) return a.t.localeCompare(b.t);
    if (nx === null) return 1;
    if (ny === null) return -1;
    if (nx === ny) return a.t.localeCompare(b.t);
    return (nx - ny) * sortDir;
  }

  // Some source synopses run a full paragraph. The table wants one scannable
  // line; the full text still shows on the film's own page.
  function oneLine(s) {
    if (s.length <= 150) return esc(s);
    var cut = s.slice(0, 150);
    var sp = cut.lastIndexOf(" ");
    if (sp > 100) cut = cut.slice(0, sp);
    return esc(cut.replace(/[\s.,;:—-]+$/, "")) + "&hellip;";
  }

  function row(f) {
    var badge =
      f.st === "Licensed"
        ? '<span class="badge badge-licensed">Licensed</span>'
        : '<span class="badge badge-available">Available</span>';
    return (
      "<tr>" +
      '<td class="c-title"><a href="films/' +
      encodeURIComponent(f.s) +
      '.html">' +
      esc(f.t) +
      "</a></td>" +
      '<td class="c-num" data-k="Year">' +
      (f.y ? esc(f.y) : '<span class="muted">&mdash;</span>') +
      "</td>" +
      '<td data-k="Genre">' +
      (f.g.length ? esc(f.g.join(", ")) : '<span class="muted">&mdash;</span>') +
      "</td>" +
      '<td class="c-num" data-k="Runtime">' +
      (f.r ? f.r + " min" : '<span class="muted">Not listed</span>') +
      "</td>" +
      '<td class="c-logline">' +
      oneLine(f.o) +
      "</td>" +
      '<td class="c-status">' +
      badge +
      "</td>" +
      "</tr>"
    );
  }

  function render() {
    var out = films.filter(matches).sort(compare);
    tbody.innerHTML = out.map(row).join("");
    empty.hidden = out.length > 0;
    var n = out.length;
    count.innerHTML =
      n === films.length
        ? "<b>" + n + "</b> titles"
        : "<b>" + n + "</b> of " + films.length + " titles";
  }

  [q, genre, decade, lang, runtime, status].forEach(function (el) {
    el.addEventListener("input", function () {
      // Any explicit language choice overrides the ?intl= deep link.
      if (el === lang) delete lang.dataset.intl;
      render();
    });
  });

  document.getElementById("reset").addEventListener("click", function () {
    [q, genre, decade, lang, runtime, status].forEach(function (el) {
      el.value = "";
    });
    delete lang.dataset.intl;
    sortKey = "t";
    sortDir = 1;
    render();
  });

  Array.prototype.forEach.call(
    document.querySelectorAll("th button[data-sort]"),
    function (btn) {
      btn.addEventListener("click", function () {
        var k = btn.dataset.sort;
        sortDir = sortKey === k ? -sortDir : 1;
        sortKey = k;
        Array.prototype.forEach.call(
          document.querySelectorAll("th button[data-sort]"),
          function (b) {
            b.parentNode.removeAttribute("aria-sort");
            b.textContent = b.textContent.replace(/\s*[↑↓]$/, "");
          }
        );
        btn.parentNode.setAttribute(
          "aria-sort",
          sortDir === 1 ? "ascending" : "descending"
        );
        btn.textContent += sortDir === 1 ? " ↑" : " ↓";
        render();
      });
    }
  );

  document.getElementById("filters").addEventListener("submit", function (ev) {
    ev.preventDefault();
  });

  render();
})();
