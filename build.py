#!/usr/bin/env python3
"""
Classic Films Vault — static site generator.

Reads data/catalog.csv and writes a complete static site to dist/.
Stdlib only; no pip install, no node_modules, no build toolchain.

    python3 build.py

To update the catalog, edit data/catalog.csv and re-run. Nothing else needs
to change.
"""

import csv
import html
import json
import os
import re
import shutil
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "catalog.csv")
ASSETS = os.path.join(HERE, "assets")
DIST = os.path.join(HERE, "dist")

# Absolute origin (+ subpath) the site is served from. Sitemaps must contain
# absolute URLs, and GitHub Pages project sites live under /<repo>/, so this
# can't be assumed to be "/". Set SITE_BASE in the deploy workflow.
SITE_BASE = os.environ.get("SITE_BASE", "").rstrip("/")

SITE_NAME = "Classic Films Vault"

# The three represented catalogs. Each is its own CSV so they stay
# independently editable and one agency's data can never disturb another's --
# data/catalog.csv in particular is the original Classic Films Vault file and
# is not rewritten by the represented-catalog import.
#
# `prefix` namespaces the slugs. Classic Films Vault keeps an empty prefix so
# its already-published URLs do not move; the newer catalogs are prefixed so
# the 18 titles carried by both agencies get distinct pages.
CATALOGS = [
    {
        "key": "classic-films-vault",
        "name": "Classic Films Vault",
        "file": "catalog.csv",
        "prefix": "",
        "blurb": "Classic Hollywood and international cinema, 1930s to today "
                 "\u2014 westerns, noir, Rathbone-era mystery, gothic horror, "
                 "and art-house landmarks.",
    },
    {
        "key": "blue-finch",
        "name": "Blue Finch Film Releasing",
        "file": "blue-finch.csv",
        "prefix": "bf",
        "blurb": "Contemporary independent features, weighted to the 2010s "
                 "and 2020s \u2014 led by horror, drama, and thriller.",
    },
    {
        "key": "sc-films",
        "name": "SC Films International",
        "file": "sc-films.csv",
        "prefix": "sc",
        "blurb": "Live action and family animation, plus documentary and "
                 "genre titles. Year and runtime data is largely absent.",
    },
]
CATALOG_BY_KEY = {c["key"]: c for c in CATALOGS}
TAGLINE = "Classic film licensing"

# The licensing copy is contractual language and is reproduced verbatim.
# The opening sentence was widened to match the actual catalog range (20 titles
# post-date 1979), rather than trimming real inventory to fit a marketing line.
LICENSING_TERMS = (
    "Classic Films Vault represents a library of 100+ films spanning classic "
    "Hollywood, international cinema, and contemporary art-house titles from "
    "the 1930s to today. Titles are available for non-exclusive licensing across "
    "streaming, broadcast, and digital platforms, with territory and term "
    "negotiated per deal. Some titles currently carry a non-exclusive license "
    "with another platform — this doesn't prevent additional licensing, and "
    "any existing arrangement will be disclosed during the inquiry process. "
    "Reach out with the titles or volume you're interested in, and we'll follow "
    "up with availability, territory, and rate details."
)

CONFIRMATION = (
    "Thanks — we've got your inquiry and will follow up within a few "
    "business days with availability and terms."
)

USE_OPTIONS = [
    "Streaming platform",
    "Broadcast",
    "Home video or digital sell-through",
    "Educational or institutional",
    "Other",
]
VOLUME_OPTIONS = [
    "Single title",
    "Small package (2–10)",
    "Full or near-full catalog",
]

# Genre groupings for the home-page anchors. Each maps to a catalog filter.
HIGHLIGHTS = [
    ("Westerns", ["Western"], "Singing cowboys, cavalry pictures, and late-cycle revisionist entries."),
    ("Mystery & noir", ["Mystery", "Film-Noir", "Crime"], "Rathbone-era Holmes, Fritz Lang thrillers, and hard-boiled studio noir."),
    # Now majority Blue Finch, so the description can no longer name only the
    # Classic Films Vault titles.
    ("Horror & sci-fi", ["Horror", "Sci-Fi"], "Corman-Poe gothics and drive-in creature features through to contemporary independent horror."),
    ("International", None, "Kurosawa, Ozu, Mizoguchi, Ray, Buñuel, Tarkovsky, and De Sica."),
]


# Marquee titles for the home-page carousel, in display order. Each entry is
# (title, catalog key): the catalog is part of the key because a title can
# legitimately exist in more than one catalog. Resolved against the CSVs at
# build time -- never a second copy of the data -- and the build fails if a
# pair stops resolving.
FEATURED = [
    ("Bicycle Thieves", "classic-films-vault"),
    ("A Bronx Tale", "blue-finch"),
    ("Stagecoach", "classic-films-vault"),
    ("Monster Island (aka Orang Ikan)", "sc-films"),
    ("M", "classic-films-vault"),
    ("Papillon", "blue-finch"),
    ("Charade", "classic-films-vault"),
    ("Dragonkeeper", "sc-films"),
    ("Dead Man's Shoes", "blue-finch"),
    ("Foreign Correspondent", "classic-films-vault"),
    ("Frances Ha", "blue-finch"),
    ("Pather Panchali", "classic-films-vault"),
]


def e(s):
    return html.escape(s or "", quote=True)


def monogram(title):
    """Initial used as placeholder art — 'The Outlaw' reads better as O."""
    t = re.sub(r"^(the|a|an)\s+", "", title.strip(), flags=re.I)
    return (t[:1] or "?").upper()


def load():
    """Every published title across all three catalogs, each tagged with its
    source catalog."""
    films = []
    skipped = 0
    seen_slugs = {}
    for cat in CATALOGS:
        path = os.path.join(HERE, "data", cat["file"])
        if not os.path.exists(path):
            raise SystemExit("missing catalog file: %s" % path)
        with open(path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        for r in rows:
            r = {k: (v or "").strip() for k, v in r.items() if k}
            # publish=no holds a title out of the catalog without deleting it
            if r.get("publish", "yes").lower() in ("no", "false", "0"):
                skipped += 1
                continue
            # Genres are "; "-separated in the Classic Films Vault file and a
            # single verbatim label in the agency files. Both land as a list.
            r["genre_list"] = [g for g in r["genres"].split("; ") if g]
            r["runtime_n"] = int(r["runtime"]) if r["runtime"].isdigit() else None
            r["catalog"] = cat["key"]
            r["catalog_name"] = cat["name"]
            if r["slug"] in seen_slugs:
                raise SystemExit(
                    "duplicate slug %r in %s and %s"
                    % (r["slug"], seen_slugs[r["slug"]], cat["file"])
                )
            seen_slugs[r["slug"]] = cat["file"]
            films.append(r)
    films.sort(key=lambda f: f["title"].lower())
    if skipped:
        print("skipping %d title(s) marked publish=no" % skipped)
    return films


def in_catalog(films, key):
    return [f for f in films if f["catalog"] == key]


# --------------------------------------------------------------------------
# layout
# --------------------------------------------------------------------------

NAV = [
    ("Home", "index.html"),
    ("Catalogs", "catalog.html"),
    ("Browse", "browse.html"),
    ("Licensing", "licensing.html"),
    ("About", "about.html"),
]


def page(title, body, current, depth=0, description=""):
    """depth=1 for pages inside films/, so asset paths resolve."""
    up = "../" * depth
    nav = []
    for label, href in NAV:
        cur = ' aria-current="page"' if href == current else ""
        cls = ' class="nav-home"' if href == "index.html" else ""
        nav.append('<a href="%s%s"%s%s>%s</a>' % (up, href, cls, cur, label))
    nav.append(
        '<a class="cta" href="%slicensing.html">'
        '<span class="cta-long">Contact us for licensing</span>'
        '<span class="cta-short">Contact</span></a>' % up
    )
    desc = description or (
        "100+ films spanning classic Hollywood, international cinema, and "
        "contemporary art-house titles, available for non-exclusive licensing "
        "across streaming, broadcast, and digital."
    )
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(desc)s">
<meta name="robots" content="index, follow">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(desc)s">
<meta property="og:type" content="website">
<link rel="icon" type="image/png" sizes="32x32" href="%(up)sassets/favicon-32.png">
<link rel="apple-touch-icon" href="%(up)sassets/favicon-180.png">
<meta name="theme-color" content="#1a1a1a">
<link rel="stylesheet" href="%(up)sassets/site.css">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-head">
  <div class="wrap">
    <a class="brand" href="%(up)sindex.html">
      <img src="%(up)sassets/logo-200.png" alt="" width="200" height="200" decoding="async">
      <span class="brand-text">
        <span class="brand-name">Classic Films Vault</span>
        <span class="mark">Licensing &amp; distribution</span>
      </span>
    </a>
    <nav class="nav" aria-label="Main">%(nav)s</nav>
  </div>
</header>
<main id="main">
%(body)s
</main>
<footer class="site-foot">
  <div class="wrap">
    <div>&copy; %(year)s Classic Films Vault. Licensing inquiries only — this site does not stream or sell films.</div>
    <div class="fnav">
      <a href="%(up)sbrowse.html">Browse titles</a>
      <a href="%(up)slicensing.html">Licensing &amp; contact</a>
      <a href="%(up)sabout.html">About</a>
    </div>
  </div>
</footer>
</body>
</html>
""" % {
        "title": e(title),
        "desc": e(desc),
        "nav": "\n      ".join(nav),
        "body": body,
        "up": up,
        "year": 2026,
    }


# --------------------------------------------------------------------------
# home
# --------------------------------------------------------------------------


def build_featured(films):
    by_key = {(f["title"].strip().lower(), f["catalog"]): f for f in films}
    cards = []
    for want, cat in FEATURED:
        f = by_key.get((want.strip().lower(), cat))
        if f is None:
            raise SystemExit(
                "featured title %r is not in the %s catalog (renamed, removed, "
                "or publish=no). Fix FEATURED in build.py or the catalog CSV."
                % (want, cat)
            )
        # Optional `poster` column: drop a filename in and the card uses the
        # real key art instead of the placeholder. No row has one yet.
        poster = f.get("poster", "").strip()
        if poster:
            art = (
                '<img src="assets/posters/%s" alt="" loading="lazy" '
                'width="300" height="450">' % e(poster)
            )
        else:
            art = '<span class="mono" aria-hidden="true">%s</span>' % e(
                monogram(f["title"])
            )
        # The full badge wording ("Licensed - non-exclusive") is too wide for a
        # card pill; the bare status reads fine at this size.
        bcls = badge(f["status"])[0]
        btxt = f["status"] or "Available"
        cards.append(
            """        <a class="film-card" href="films/%(slug)s.html" title="%(title)s">
          <span class="poster">
            %(art)s
            <span class="status-dot %(bcls)s">%(btxt)s</span>
          </span>
          <span class="cap">
            <b>%(title)s</b>
            <span class="cap-year">%(year)s</span>
            <span class="rep-tag rep-tag-sm"><span>Represented by</span> %(cat)s</span>
          </span>
        </a>"""
            % {
                "slug": e(f["slug"]),
                "art": art,
                "bcls": e(bcls),
                "btxt": e(btxt),
                "title": e(f["title"]),
                # .muted fails contrast at this size; .cap-year's own colour
                # passes and this is real information, not decoration.
                "year": e(f["year"]) or "Year not listed",
                "cat": e(f["catalog_name"]),
            }
        )

    return """
<section class="section section-white">
  <div class="wrap">
    <div class="featured-head">
      <h2>Featured titles</h2>
      <a class="all-link" href="browse.html">View all %(total)d titles &rsaquo;</a>
    </div>
    <div class="carousel" data-carousel>
      <button type="button" class="carousel-btn prev" aria-label="Scroll featured titles left">&lsaquo;</button>
      <div class="carousel-track" tabindex="0" role="group" aria-label="Featured titles">
%(cards)s
      </div>
      <button type="button" class="carousel-btn next" aria-label="Scroll featured titles right">&rsaquo;</button>
    </div>
  </div>
</section>
""" % {"cards": "\n".join(cards), "total": len(films)}


def build_home(films):
    total = len(films)
    intl = sum(1 for f in films if f["language"] and f["language"] != "English")

    tiles = []
    for label, genres, sub in HIGHLIGHTS:
        if genres is None:
            count = intl
            href = "browse.html?intl=1"
        else:
            count = sum(1 for f in films if any(g in f["genre_list"] for g in genres))
            href = "browse.html?genre=" + urllib.parse.quote(genres[0])
        tiles.append(
            """      <a class="tile" href="%s">
        <span class="count">%d</span>
        <span class="label">%s</span>
        <span class="sub">%s</span>
      </a>"""
            % (href, count, e(label), e(sub))
        )

    decades = {}
    for f in films:
        if f["decade"]:
            decades[f["decade"]] = decades.get(f["decade"], 0) + 1
    chips = "".join(
        '<a class="decade-chip" href="browse.html?decade=%s"><b>%d</b> from the %s</a>'
        % (d, decades[d], d)
        for d in sorted(decades)
    )

    licensed = sum(1 for f in films if f["status"] == "Licensed")

    # The combined number headlines, but each catalog's own count stays on the
    # page: a buyer should never have to guess where a title comes from.
    split = "\n".join(
        '      <li><a href="browse.html?catalog=%s"><b>%d</b> %s</a></li>'
        % (urllib.parse.quote(c["key"]), len(in_catalog(films, c["key"])), e(c["name"]))
        for c in CATALOGS
    )

    body = """
<section class="hero">
  <div class="wrap">
    <p class="eyebrow">Classic Films Vault</p>
    <h1>%(total)d titles available for licensing</h1>
    <p class="pitch">Three represented catalogs &mdash; classic Hollywood and
      international cinema, contemporary independent features, and live action
      and family animation &mdash; licensed across streaming, broadcast, and
      digital platforms.</p>
    <ul class="hero-split">
%(split)s
    </ul>
    <div class="hero-actions">
      <a class="btn btn-gold" href="licensing.html">Contact us for licensing</a>
      <a class="btn btn-ghost" href="catalog.html">Browse the catalogs</a>
    </div>
  </div>
</section>
%(featured)s
<section class="section section-cream">
  <div class="wrap">
    <div class="rule-head"><h2>What&rsquo;s in the library</h2></div>
    <div class="tiles">
%(tiles)s
    </div>
    <div class="decades">%(chips)s</div>
  </div>
</section>

<section class="section section-white">
  <div class="wrap">
    <div class="rule-head"><h2>How licensing works</h2></div>
    <div class="tiles">
      <div class="tile">
        <span class="label">Three catalogs, one inquiry</span>
        <span class="sub">%(cfv)d titles in the Classic Films Vault library, plus
          %(bf)d represented for Blue Finch Film Releasing and %(sc)d for SC Films
          International. Every title page says which.</span>
      </div>
      <div class="tile">
        <span class="label">Terms stated, not implied</span>
        <span class="sub">Classic Films Vault titles are offered non-exclusively,
          territory and term per deal. Agency-represented titles carry no assumed
          position &mdash; availability is confirmed per inquiry.</span>
      </div>
      <div class="tile">
        <span class="label">Nothing hidden</span>
        <span class="sub">%(licensed)d titles currently carry a non-exclusive licence
          with another platform. They are flagged in the catalog and remain available
          to license.</span>
      </div>
      <div class="tile">
        <span class="label">Single titles to full catalog</span>
        <span class="sub">Package one title, a themed bundle, or the whole library.
          Tell us the volume and we&rsquo;ll come back with rates.</span>
      </div>
    </div>
    <p style="margin-top:32px">
      <a class="btn btn-solid" href="licensing.html">Start a licensing inquiry</a>
    </p>
  </div>
</section>
<script src="assets/carousel.js"></script>
""" % {
        "total": total,
        "split": split,
        "cfv": len(in_catalog(films, "classic-films-vault")),
        "bf": len(in_catalog(films, "blue-finch")),
        "sc": len(in_catalog(films, "sc-films")),
        "featured": build_featured(films),
        "tiles": "\n".join(tiles),
        "chips": chips,
        "licensed": licensed,
    }
    return page(
        "Classic Films Vault \u2014 %d titles for licensing" % total,
        body,
        "index.html",
    )


# --------------------------------------------------------------------------
# catalog
# --------------------------------------------------------------------------


def build_catalog(films):
    """Landing view: one card per represented catalog."""
    cards = []
    for cat in CATALOGS:
        mine = in_catalog(films, cat["key"])
        years = sorted(int(f["year"]) for f in mine if f["year"].isdigit())
        span = "%d\u2013%d" % (years[0], years[-1]) if years else ""
        top = {}
        for f in mine:
            for g in f["genre_list"]:
                top[g] = top.get(g, 0) + 1
        leading = ", ".join(
            g for g, _ in sorted(top.items(), key=lambda kv: (-kv[1], kv[0]))[:4]
        )
        facts = []
        if span:
            facts.append("Years %s" % span)
        if leading:
            facts.append("Mostly %s" % leading)
        cards.append(
            """      <a class="cat-card" href="browse.html?catalog=%(key)s">
        <span class="cat-count">%(n)d</span>
        <span class="cat-name">%(name)s</span>
        <span class="cat-blurb">%(blurb)s</span>
        <span class="cat-facts">%(facts)s</span>
        <span class="cat-go">Browse this catalog &rsaquo;</span>
      </a>"""
            % {
                "key": e(cat["key"]),
                "n": len(mine),
                "name": e(cat["name"]),
                "blurb": e(cat["blurb"]),
                "facts": e(" \u00b7 ".join(facts)),
            }
        )

    body = """
<section class="section section-cream">
  <div class="wrap">
    <div class="rule-head"><h1>Catalogs</h1></div>
    <p class="lede">We represent %(total)d titles across three catalogs. Pick one
      to browse it on its own, or search the whole library at once &mdash; the
      same filters apply either way.</p>

    <div class="cat-cards">
%(cards)s
    </div>

    <p style="margin-top:34px">
      <a class="btn btn-solid" href="browse.html">Browse all %(total)d titles</a>
    </p>
  </div>
</section>
""" % {"cards": "\n".join(cards), "total": len(films)}

    return page(
        "Catalogs \u2014 %s" % SITE_NAME,
        body,
        "catalog.html",
        description="Three represented catalogs totalling %d titles: %s."
        % (len(films), ", ".join(c["name"] for c in CATALOGS)),
    )


def build_browse(films):
    """The single browse UI, shared by every catalog."""
    genres = sorted({g for f in films for g in f["genre_list"]})
    decades = sorted({f["decade"] for f in films if f["decade"]})
    langs = sorted({f["language"] for f in films if f["language"]})
    statuses = sorted({f["status"] for f in films if f["status"]})

    def opts(values):
        return "".join('<option value="%s">%s</option>' % (e(v), e(v)) for v in values)

    cat_opts = "".join(
        '<option value="%s">%s (%d)</option>'
        % (e(c["key"]), e(c["name"]), len(in_catalog(films, c["key"])))
        for c in CATALOGS
    )

    payload = [
        {
            "s": f["slug"],
            "t": f["title"],
            "y": f["year"],
            "d": f["decade"],
            "g": f["genre_list"],
            "l": f["language"],
            "r": f["runtime_n"],
            "o": f["logline"],
            "st": f["status"],
            "c": f["catalog"],
            "cn": f["catalog_name"],
        }
        for f in films
    ]

    body = """
<section class="section section-cream">
  <div class="wrap">
    <div class="rule-head"><h1>Browse titles</h1></div>
    <p class="lede">%(total)d titles across all three catalogs.
      <a href="catalog.html">Browse by catalog</a> instead, or filter below.
      Every row shows which catalog represents the title.</p>

    <form class="filters" id="filters" role="search" aria-label="Filter titles">
      <div class="filter-grid">
        <div class="field search-field">
          <label for="q">Search title or logline</label>
          <input type="search" id="q" name="q" placeholder="e.g. Stagecoach, Holmes, uranium" autocomplete="off">
        </div>
        <div class="field">
          <label for="catalog">Catalog</label>
          <select id="catalog"><option value="">All catalogs</option>%(cats)s</select>
        </div>
        <div class="field">
          <label for="genre">Genre</label>
          <select id="genre"><option value="">All genres</option>%(genres)s</select>
        </div>
        <div class="field">
          <label for="decade">Decade</label>
          <select id="decade">
            <option value="">All decades</option>%(decades)s
            <option value="__none">Not listed</option>
          </select>
        </div>
        <div class="field">
          <label for="lang">Language</label>
          <select id="lang">
            <option value="">All languages</option>%(langs)s
            <option value="__none">Not specified</option>
          </select>
        </div>
        <div class="field">
          <label for="runtime">Runtime</label>
          <select id="runtime">
            <option value="">Any runtime</option>
            <option value="0-79">Under 80 min</option>
            <option value="80-99">80&ndash;99 min</option>
            <option value="100-119">100&ndash;119 min</option>
            <option value="120-999">120 min and over</option>
            <option value="__none">Not listed</option>
          </select>
        </div>
        <div class="field">
          <label for="status">Licensing status</label>
          <select id="status"><option value="">Any status</option>%(statuses)s</select>
        </div>
      </div>
      <div class="filter-foot">
        <p class="result-count" id="count" role="status" aria-live="polite"></p>
        <button type="button" class="link-btn" id="reset">Clear all filters</button>
      </div>
    </form>

    <div class="table-scroll">
      <table class="catalog">
        <thead>
          <tr>
            <th scope="col"><button type="button" data-sort="t">Title</button></th>
            <th scope="col"><button type="button" data-sort="y">Year</button></th>
            <th scope="col">Genre</th>
            <th scope="col"><button type="button" data-sort="r">Runtime</button></th>
            <th scope="col">Logline</th>
            <th scope="col">Represented by</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody id="rows"></tbody>
      </table>
      <div class="empty" id="empty" hidden>
        <p><strong>No titles match those filters.</strong></p>
        <p>Try clearing a filter, or <a href="licensing.html">ask us about the full catalog</a>.</p>
      </div>
    </div>
  </div>
</section>
<script id="catalog-data" type="application/json">%(json)s</script>
<script src="assets/catalog.js"></script>
""" % {
        "total": len(films),
        "cats": cat_opts,
        "genres": opts(genres),
        "decades": opts(decades),
        "langs": opts(langs),
        "statuses": opts(statuses),
        # </script> can't appear inside an inline JSON block.
        "json": json.dumps(payload, separators=(",", ":")).replace("<", "\\u003c"),
    }
    return page(
        "Browse titles \u2014 %s" % SITE_NAME,
        body,
        "browse.html",
        description="Search and filter all %d represented titles by catalog, "
        "genre, decade, language, and runtime." % len(films),
    )


# --------------------------------------------------------------------------
# film detail
# --------------------------------------------------------------------------


# Three rights positions, and they are not interchangeable. "Represented"
# means exactly that: the agency carries the title. It is not a claim that the
# title is unencumbered, which is what "Available" asserts.
BADGES = {
    "Available": ("badge-available", "Available"),
    "Licensed": ("badge-licensed", "Licensed \u2014 non-exclusive"),
    "Represented": ("badge-represented", "Represented"),
}


def badge(status):
    return BADGES.get(status, ("badge-available", status or "Available"))


def build_film(f, films):
    badge_cls, badge_txt = badge(f["status"])

    meta = []
    if f["year"]:
        meta.append(e(f["year"]))
    if f["genre_list"]:
        meta.append(e(", ".join(f["genre_list"])))
    if f["runtime_n"]:
        meta.append("%d min" % f["runtime_n"])
    if f["language"]:
        meta.append(e(f["language"]))
    meta_html = '<span class="sep">/</span>'.join("<span>%s</span>" % m for m in meta)

    rep = (
        '<a class="rep-tag" href="../browse.html?catalog=%s">'
        '<span>Represented by</span> %s</a>'
        % (urllib.parse.quote(f["catalog"]), e(f["catalog_name"]))
    )

    spec = [("Represented by", f["catalog_name"])]
    spec.append(("Year", f["year"] or "Not listed"))
    spec.append(("Genre", ", ".join(f["genre_list"]) or "Not listed"))
    spec.append(("Language", f["language"] or "Not specified"))
    spec.append(
        ("Runtime", "%d minutes" % f["runtime_n"] if f["runtime_n"] else "Not listed")
    )
    if f["credit"]:
        spec.append(("Note", f["credit"]))
    spec.append(("Licensing status", badge_txt))
    if f["territory"]:
        spec.append(("Existing licence territory", f["territory"]))
    spec_html = "\n    ".join(
        "<div><dt>%s</dt><dd>%s</dd></div>" % (e(k), e(v)) for k, v in spec
    )

    tags = "".join(
        '<a class="tag" href="../browse.html?genre=%s">%s</a>'
        % (urllib.parse.quote(g), e(g))
        for g in f["genre_list"]
    )
    if f["decade"]:
        tags += '<a class="tag" href="../browse.html?decade=%s">%s</a>' % (
            f["decade"],
            f["decade"],
        )

    synopsis = (
        '<p class="synopsis">%s</p>' % e(f["logline"])
        if f["logline"]
        else '<p class="synopsis muted">No synopsis on file for this title. '
        'We can supply one on request.</p>'
    )

    inquire = "../licensing.html?title=" + urllib.parse.quote(f["title"])

    body = """
<section class="film-head">
  <div class="wrap">
    <p class="crumbs"><a href="../index.html">Home</a> &rsaquo;
      <a href="../browse.html">Browse</a> &rsaquo; %(title)s</p>
    <h1>%(title)s</h1>
    <div class="film-meta">%(meta)s</div>
    <span class="badge %(bcls)s badge-lg">%(btxt)s</span>
    %(rep)s
  </div>
</section>

<div class="wrap">
  <div class="film-body">
    <div>
      <h2>Synopsis</h2>
      %(synopsis)s

      <h2>Details</h2>
      <dl class="spec">
    %(spec)s
      </dl>

      <h2 style="margin-top:34px">Browse similar</h2>
      <div class="tag-row">%(tags)s</div>
    </div>

    <aside class="aside-card">
      <h2>Licensing</h2>
      <p>%(licence_note)s</p>
      <p>Territory and term are negotiated per deal. Send us this title and
        we&rsquo;ll come back with availability and rates.</p>
      <a class="btn btn-solid" href="%(inquire)s">Inquire about this title</a>
    </aside>
  </div>
</div>
""" % {
        "title": e(f["title"]),
        "meta": meta_html,
        "bcls": badge_cls,
        "btxt": e(badge_txt),
        "synopsis": synopsis,
        "rep": rep,
        "spec": spec_html,
        "tags": tags,
        "licence_note": e(f["licence_note"]),
        "inquire": e(inquire),
    }

    year = " (%s)" % f["year"] if f["year"] else ""
    return page(
        "%s%s — licensing — %s" % (f["title"], year, SITE_NAME),
        body,
        "",
        depth=1,
        description="%s%s \u2014 %srepresented by %s. Available for licensing."
        % (
            f["title"],
            year,
            (f["logline"][:150] + " ") if f["logline"] else "",
            f["catalog_name"],
        ),
    )


# --------------------------------------------------------------------------
# licensing / contact
# --------------------------------------------------------------------------


def build_licensing(films):
    def opts(values):
        return "".join('<option value="%s">%s</option>' % (e(v), e(v)) for v in values)

    body = """
<section class="section section-cream">
  <div class="wrap">
    <div class="rule-head"><h1>Licensing &amp; contact</h1></div>

    <div class="prose">
      <p>%(terms)s</p>
      <p>Alongside that library we represent %(bf)d titles for Blue Finch Film
        Releasing and %(sc)d for SC Films International &mdash; %(total)d titles
        in all. The paragraph above sets out the terms for the Classic Films
        Vault library specifically; for agency-represented titles we hold no
        assumed rights position, and availability, territory, and terms are
        confirmed per inquiry. Every title page states which catalog the film
        comes from.</p>
    </div>

    <h3 style="font-family:var(--serif);font-size:24px;margin:44px 0 18px">Send an inquiry</h3>

    <div class="form-card">
      <div class="notice notice-ok" id="ok" hidden role="status">%(confirm)s</div>
      <div class="notice notice-err" id="err" hidden role="alert"></div>
      <div class="notice notice-warn" id="unconfigured" hidden>
        <strong>This form isn&rsquo;t connected yet.</strong> Add your form endpoint in
        <code>assets/config.js</code> to start receiving inquiries. See
        <code>README.md</code> for the two-minute setup.
      </div>

      <form id="inquiry" novalidate>
        <div class="form-grid">
          <div class="field">
            <label for="name">Name <span class="req">*</span></label>
            <input type="text" id="name" name="name" required autocomplete="name">
            <p class="err-text" data-err="name" hidden>Please enter your name.</p>
          </div>
          <div class="field">
            <label for="company">Company <span class="req">*</span></label>
            <input type="text" id="company" name="company" required autocomplete="organization">
            <p class="err-text" data-err="company" hidden>Please enter your company.</p>
          </div>
          <div class="field full">
            <label for="email">Email <span class="req">*</span></label>
            <input type="email" id="email" name="email" required autocomplete="email">
            <p class="err-text" data-err="email" hidden>Please enter a valid email address.</p>
          </div>
          <div class="field full">
            <label for="titles">Titles of interest</label>
            <input type="text" id="titles" name="titles"
              placeholder="e.g. Stagecoach, M, or 'browsing the full catalog'">
            <p class="hint">Coming from a film page? We&rsquo;ll fill this in for you.</p>
          </div>
          <div class="field">
            <label for="use">Intended use</label>
            <select id="use" name="use">
              <option value="">Select&hellip;</option>%(uses)s
            </select>
          </div>
          <div class="field">
            <label for="volume">Estimated volume</label>
            <select id="volume" name="volume">
              <option value="">Select&hellip;</option>%(vols)s
            </select>
          </div>
          <div class="field full">
            <label for="message">Message</label>
            <textarea id="message" name="message" placeholder="Anything else we should know?"></textarea>
          </div>
        </div>
        <div class="form-foot">
          <button type="submit" class="btn btn-solid" id="submit">Send inquiry</button>
          <span class="hint" id="status-line"></span>
        </div>
      </form>
    </div>

    <div class="prose" style="margin-top:44px">
      <h2>What happens next</h2>
      <p>We review every inquiry and reply within a few business days with
        availability, territory options, and rates. You&rsquo;ll get an
        acknowledgement by email as soon as you submit. Inquiries are handled by
        email only &mdash; there&rsquo;s no live chat or booking calendar to
        navigate.</p>
    </div>
  </div>
</section>
<script src="assets/config.js"></script>
<script src="assets/inquiry.js"></script>
""" % {
        "terms": e(LICENSING_TERMS),
        "total": len(films),
        "bf": len(in_catalog(films, "blue-finch")),
        "sc": len(in_catalog(films, "sc-films")),
        "confirm": e(CONFIRMATION),
        "uses": opts(USE_OPTIONS),
        "vols": opts(VOLUME_OPTIONS),
    }
    return page(
        "Licensing & contact — %s" % SITE_NAME,
        body,
        "licensing.html",
        description="Licensing terms and inquiry form for the Classic Films Vault "
        "library of 100+ classic films.",
    )


# --------------------------------------------------------------------------
# about
# --------------------------------------------------------------------------


def build_about(films):
    cfv = in_catalog(films, "classic-films-vault")
    langs = sorted(
        {f["language"] for f in cfv if f["language"] and f["language"] != "English"}
    )
    body = """
<section class="section section-cream">
  <div class="wrap">
    <div class="rule-head"><h1>About the collection</h1></div>
    <div class="prose">
      <p>We represent %(total)d titles across three catalogs: our own Classic
        Films Vault library, and two agency catalogs we carry on behalf of
        Blue Finch Film Releasing and SC Films International. Every title page
        states which catalog it comes from.</p>

      <h2>Classic Films Vault</h2>
      <p>%(cfv)d titles of classic Hollywood and international cinema,
        concentrated in the 1930s through the 1970s. The American side runs deep
        on genre pictures: B-westerns and singing-cowboy series, studio film noir,
        the Rathbone-era Sherlock Holmes mysteries, and the gothic horror and
        drive-in science fiction that followed them. The international side
        gathers landmark work from Japan, Italy, France, India, China, Russia,
        and Spain &mdash; films by Kurosawa, Ozu, Mizoguchi, Satyajit Ray,
        De Sica, Bu&ntilde;uel, and Tarkovsky among them, across %(nlang)d
        languages beyond English. These titles are offered for non-exclusive
        licensing across streaming, broadcast, and digital platforms, with
        territory and term negotiated per deal.</p>

      <h2>Represented catalogs</h2>
      <p>%(bf)d titles for Blue Finch Film Releasing &mdash; contemporary
        independent features, weighted to the 2010s and 2020s, led by horror,
        drama, and thriller. %(sc)d titles for SC Films International &mdash;
        live action and family animation, with documentary and genre titles
        alongside. We hold no assumed rights position on these: availability,
        territory, and terms are confirmed per inquiry.</p>

      <p>We are a licensing and distribution operation only &mdash; this site is
        a catalog and a contact form, not a streaming service.</p>

      <p><a class="btn btn-solid" href="catalog.html">Browse the catalogs</a></p>
    </div>
  </div>
</section>
""" % {
        "total": len(films),
        "cfv": len(cfv),
        "bf": len(in_catalog(films, "blue-finch")),
        "sc": len(in_catalog(films, "sc-films")),
        "nlang": len(langs),
    }
    return page("About \u2014 %s" % SITE_NAME, body, "about.html")


# --------------------------------------------------------------------------


def main():
    films = load()
    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    os.makedirs(os.path.join(DIST, "films"))
    shutil.copytree(ASSETS, os.path.join(DIST, "assets"))

    def write(rel, content):
        path = os.path.join(DIST, rel)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)

    write("index.html", build_home(films))
    write("catalog.html", build_catalog(films))
    write("browse.html", build_browse(films))
    write("licensing.html", build_licensing(films))
    write("about.html", build_about(films))
    for f in films:
        write(os.path.join("films", f["slug"] + ".html"), build_film(f, films))

    # sitemap + robots help buyers' procurement teams find titles by search
    urls = ["index.html", "catalog.html", "browse.html", "licensing.html", "about.html"]
    urls += ["films/%s.html" % f["slug"] for f in films]
    if SITE_BASE:
        write(
            "sitemap.xml",
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "".join(
                "  <url><loc>%s/%s</loc></url>\n" % (SITE_BASE, u) for u in urls
            )
            + "</urlset>\n",
        )
        write(
            "robots.txt",
            "User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n" % SITE_BASE,
        )
    else:
        # Without a known origin a sitemap would carry wrong URLs, which is
        # worse than shipping none.
        write("robots.txt", "User-agent: *\nAllow: /\n")
        urls = urls[:0] or urls

    print("built %d pages into dist/" % (len(urls) + (2 if SITE_BASE else 1)))
    if not SITE_BASE:
        print("  no SITE_BASE set — sitemap.xml skipped")
    print("  %d film pages" % len(films))
    print("  preview:  python3 -m http.server -d dist 8000")


if __name__ == "__main__":
    main()
