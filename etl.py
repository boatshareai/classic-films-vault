#!/usr/bin/env python3
"""
Build data/catalog.csv from the two source spreadsheets.

Sources (in ../, i.e. the CLASSICFILMS folder):
  ClassicFilms_Usable4YouTube.xlsx  -> 70 titles under the VA Media
                                       non-exclusive YouTube licence ("Licensed")
  2024-01-04.KR-Avails (2).xlsx     -> 106 titles, no current licence ("Available")

Run this only when the spreadsheets change. Day-to-day catalog edits should be
made directly in data/catalog.csv, which is the source of truth for the site.

Stdlib only -- no pip install required.
"""

import csv
import os
import re
import sys
import zipfile
from xml.etree import ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
OUT = os.path.join(HERE, "data", "catalog.csv")

NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

# Genre cells in the VA sheet carry editorial asides, e.g.
# "Thriller, War (Hitchcock)" or "Drama, War (TV movie)". Pull them out so the
# genre facet stays clean and the aside can be shown as a credit note instead.
ASIDE = re.compile(r"\s*\(([^)]*)\)\s*$")

CANON_GENRE = {
    "film-noir": "Film-Noir",
    "noir": "Film-Noir",
    "sci-fi": "Sci-Fi",
    "scifi": "Sci-Fi",
    "swashbuckler": "Adventure",
    "musical": "Musical",
    "music": "Music",
}


def col_idx(ref):
    letters = re.match(r"([A-Z]+)", ref).group(1)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def shared_strings(z):
    try:
        raw = z.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    out = []
    for si in ET.fromstring(raw).findall("m:si", NS):
        out.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
    return out


def rows(path):
    """Yield each sheet row as a list of trimmed cell strings."""
    z = zipfile.ZipFile(path)
    ss = shared_strings(z)
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = {
        r.get("Id"): r.get("Target")
        for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    }
    sheet = wb.find("m:sheets", NS)[0]
    target = rels[sheet.get("{%s}id" % NS["r"])].lstrip("/")
    if not target.startswith("xl/"):
        target = "xl/" + target
    root = ET.fromstring(z.read(target))
    for row in root.iter("{%s}row" % NS["m"]):
        cells = {}
        for c in row.findall("m:c", NS):
            t, v = c.get("t"), c.find("m:v", NS)
            inline = c.find("m:is", NS)
            if t == "s" and v is not None:
                val = ss[int(v.text)]
            elif t == "inlineStr" and inline is not None:
                val = "".join(x.text or "" for x in inline.iter("{%s}t" % NS["m"]))
            elif v is not None:
                val = v.text
            else:
                val = ""
            cells[col_idx(c.get("r"))] = (val or "").strip()
        if cells:
            width = max(cells) + 1
            yield [cells.get(i, "") for i in range(width)]


def get(row, i):
    return row[i].strip() if i < len(row) else ""


DIRECTORS = {"hitchcock", "fritz lang", "john ford", "orson welles", "sam fuller"}


def label_aside(aside):
    """The VA sheet's parenthetical is a director, a format, or a series tag."""
    if not aside:
        return ""
    a = aside.strip()
    if a.lower() in DIRECTORS:
        return "Directed by %s" % a
    if a.lower() == "tv movie":
        return "Made for television"
    return "Part of the %s series" % a


def split_genres(cell):
    """-> (clean genre list, editorial aside or '')"""
    aside = ""
    m = ASIDE.search(cell)
    if m:
        aside = m.group(1).strip()
        cell = cell[: m.start()]
    genres = []
    for g in cell.split(","):
        g = g.strip()
        if not g:
            continue
        g = CANON_GENRE.get(g.lower(), g.title() if g.islower() else g)
        if g not in genres:
            genres.append(g)
    return genres, aside


# Titles that are the same film under two different names across the sheets.
# The VA sheet prefixes the Rathbone mysteries with "Sherlock Holmes"; the
# avails sheet uses the release titles.
def match_key(title, year):
    t = title.lower().strip()
    t = re.sub(r"^sherlock holmes(?:\s+and\s+the|\s+and\s+a|\s*:|\s+in)?\s+", "", t)
    t = re.sub(r"^the\s+", "", t)
    t = re.sub(r"[^a-z0-9]+", "", t)
    return (t, year)


def slugify(title, year):
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return "%s-%s" % (s, year) if year else s


# Some source rows carry an internal research note where the synopsis should
# be. Those are never buyer-facing copy, so they are dropped at import rather
# than imported and hidden -- the spreadsheets remain the record for them.
INTERNAL_NOTE = re.compile(r"UNCONFIRMED|could not verify|mistranscription", re.I)


def publishable(f):
    return not INTERNAL_NOTE.search(f["logline"] or "")


def decade(year):
    if not year:
        return ""
    return "%ds" % (int(year) // 10 * 10)


def main():
    va_path = os.path.join(SRC, "ClassicFilms_Usable4YouTube.xlsx")
    kr_path = os.path.join(SRC, "2024-01-04.KR-Avails (2).xlsx")
    for p in (va_path, kr_path):
        if not os.path.exists(p):
            sys.exit("missing source spreadsheet: %s" % p)

    films = {}
    order = []

    def upsert(key, rec):
        if key in films:
            cur = films[key]
            for k, v in rec.items():
                # First writer wins on licensing/logline; fill blanks otherwise.
                if v and not cur.get(k):
                    cur[k] = v
            return cur
        films[key] = rec
        order.append(key)
        return rec

    # --- VA Media Schedule 1: currently licensed, non-exclusive, YouTube -----
    va = list(rows(va_path))
    for row in va[1:]:
        title = get(row, 0)
        if not title:
            continue
        year = get(row, 1)
        genres, aside = split_genres(get(row, 2))
        upsert(
            match_key(title, year),
            {
                "title": title,
                "year": year,
                "genres": genres,
                "language": "",
                "runtime": get(row, 3),
                "logline": get(row, 4),
                "status": "Licensed",
                "licence_note": "Non-exclusive YouTube licence (VA Media). "
                "Available for additional licensing.",
                "territory": get(row, 5),
                "credit": label_aside(aside),
            },
        )

    # --- Avails list: no current licence ------------------------------------
    kr = list(rows(kr_path))
    for row in kr[1:]:
        title = get(row, 2) or get(row, 3)
        if not title:
            continue
        year = get(row, 7)
        genres, aside = split_genres(get(row, 6))
        rec = upsert(
            match_key(title, year),
            {
                "title": title,
                "year": year,
                "genres": genres,
                "language": get(row, 8),
                "runtime": get(row, 9),
                "logline": get(row, 11),
                "status": "Available",
                "licence_note": "No current licence on this title. "
                "Available across all platforms and territories.",
                "territory": "",
                "credit": label_aside(aside),
            },
        )
        # The avails sheet carries the better metadata; let it fill gaps on
        # titles that appear in both (runtime, language, synopsis).
        for k in ("language", "runtime", "logline"):
            v = get(row, {"language": 8, "runtime": 9, "logline": 11}[k])
            if v and not rec.get(k):
                rec[k] = v
        if not rec.get("genres"):
            rec["genres"] = genres

    # --- emit ---------------------------------------------------------------
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    cols = [
        "slug",
        "title",
        "year",
        "decade",
        "genres",
        "language",
        "runtime",
        "logline",
        "status",
        "licence_note",
        "territory",
        "credit",
        "publish",
    ]
    seen_slugs = set()
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for key in sorted(order, key=lambda k: films[k]["title"].lower()):
            f = films[key]
            if not publishable(f):
                continue
            slug = slugify(f["title"], f["year"])
            n = 2
            while slug in seen_slugs:
                slug = "%s-%d" % (slugify(f["title"], f["year"]), n)
                n += 1
            seen_slugs.add(slug)
            runtime = f["runtime"]
            runtime = runtime if re.fullmatch(r"\d+", runtime or "") else ""
            w.writerow(
                {
                    "slug": slug,
                    "title": f["title"],
                    "year": f["year"],
                    "decade": decade(f["year"]),
                    "genres": "; ".join(f["genres"]),
                    "language": f["language"],
                    "runtime": runtime,
                    "logline": f["logline"],
                    "status": f["status"],
                    "licence_note": f["licence_note"],
                    "territory": f["territory"],
                    "credit": f["credit"],
                    "publish": "yes",
                }
            )

    pub = {k: f for k, f in films.items() if publishable(f)}
    lic = sum(1 for f in pub.values() if f["status"] == "Licensed")
    print("wrote %s" % OUT)
    print("  %d titles  (%d licensed, %d available)" % (len(pub), lic, len(pub) - lic))
    va_n = sum(1 for r in va[1:] if get(r, 0))
    kr_n = sum(1 for r in kr[1:] if get(r, 2) or get(r, 3))
    print("  from %d VA rows + %d avails rows, %d titles appeared in both"
          % (va_n, kr_n, va_n + kr_n - len(films)))
    outside = sum(1 for f in films.values()
                  if f["year"] and not (1930 <= int(f["year"]) <= 1979))
    print("  %d titles fall outside the 1930s-1970s range in the site copy" % outside)
    missing_rt = sum(1 for f in films.values() if not re.fullmatch(r"\d+", f["runtime"] or ""))
    missing_lang = sum(1 for f in films.values() if not f["language"])
    no_year = sum(1 for f in films.values() if not f["year"])
    print("  gaps: runtime %d, language %d, year %d" % (missing_rt, missing_lang, no_year))
    held = [f["title"] for f in films.values() if not publishable(f)]
    if held:
        print("  dropped %d row(s) carrying an internal note instead of a "
              "synopsis" % len(held))


if __name__ == "__main__":
    main()
