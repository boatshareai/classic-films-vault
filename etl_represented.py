#!/usr/bin/env python3
"""
Build data/blue-finch.csv and data/sc-films.csv from
../Blue_Finch_SC_Films_Catalogs.xlsx.

Kept separate from etl.py so the Classic Films Vault import and its
data/catalog.csv are untouched by anything here.

Source columns: Title, Year, Genre, Runtime (min), Logline,
                Represented by, License status, Notes

Deliberate non-transformations
------------------------------
* Runtime and Logline are the literal string "Not listed" for all 298 rows.
  They are written out EMPTY so the site renders its usual "Not listed"
  placeholder. Nothing is inferred or generated to fill them.
* Year is absent for 85 of the 89 SC Films titles. Left empty; the decade
  filter skips those rows exactly as it already does elsewhere.
* Genre labels are carried over VERBATIM as a single value ("Live Action",
  "Crime Thriller", "Family Animation"). They are not split on whitespace --
  "Live Action" is a format, not Live + Action -- so splitting would invent
  genres the source never asserted.
* The 18 titles that appear in both agency lists are imported twice, once
  under each catalog, and flagged cross_listed=yes. They are NOT merged or
  deduplicated: which agency holds current rights is a human decision.
  The flag is a neutral marker; the source spreadsheet's Notes column holds
  the full wording.

Stdlib only.
"""

import csv
import os
import re
import sys

from etl import rows, get, slugify, decade  # shared xlsx reader

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "Blue_Finch_SC_Films_Catalogs.xlsx")

# agency name in the sheet -> (output file, slug prefix)
AGENCIES = {
    "Blue Finch Film Releasing": ("blue-finch.csv", "bf"),
    "SC Films International": ("sc-films.csv", "sc"),
}

COLS = [
    "slug", "title", "year", "decade", "genres", "language", "runtime",
    "logline", "status", "licence_note", "territory", "credit", "publish",
    "cross_listed",
]

# The sheet uses this literal where a value is simply absent.
BLANK = {"", "not listed", "n/a", "none", "-"}


def val(row, i):
    v = get(row, i)
    return "" if v.strip().lower() in BLANK else v.strip()


def main():
    if not os.path.exists(SRC):
        sys.exit("missing source spreadsheet: %s" % SRC)

    src = list(rows(SRC))
    records = []
    for row in src[1:]:
        title = val(row, 0)
        if not title:
            continue
        agency = get(row, 5).strip()
        if agency not in AGENCIES:
            sys.exit("unknown 'Represented by' value: %r" % agency)
        records.append(
            {
                "title": title,
                "year": val(row, 1),
                "genre": val(row, 2),
                "runtime": val(row, 3),     # always empty in this source
                "logline": val(row, 4),     # always empty in this source
                "agency": agency,
                "notes": get(row, 7).strip(),
            }
        )

    # A title carried by both agencies. Computed from the data rather than
    # parsed out of the Notes prose, so the flag can't drift from reality.
    seen = {}
    for r in records:
        seen.setdefault(r["title"].strip().lower(), set()).add(r["agency"])
    cross = {t for t, a in seen.items() if len(a) > 1}

    written = {}
    for agency, (fname, prefix) in AGENCIES.items():
        mine = [r for r in records if r["agency"] == agency]
        mine.sort(key=lambda r: r["title"].lower())
        out = os.path.join(HERE, "data", fname)
        slugs = set()
        with open(out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=COLS)
            w.writeheader()
            for r in mine:
                # Prefixed so the two agencies' copies of a shared title get
                # distinct URLs, and so nothing can collide with the existing
                # Classic Films Vault slugs, which must not change.
                base = "%s-%s" % (prefix, slugify(r["title"], r["year"]))
                slug, n = base, 2
                while slug in slugs:
                    slug = "%s-%d" % (base, n)
                    n += 1
                slugs.add(slug)
                w.writerow(
                    {
                        "slug": slug,
                        "title": r["title"],
                        "year": r["year"],
                        "decade": decade(r["year"]) if r["year"] else "",
                        "genres": r["genre"],
                        "language": "",
                        "runtime": r["runtime"],
                        "logline": r["logline"],
                        "status": "Represented",
                        "licence_note": "Represented by %s. Availability, "
                        "territory, and terms are confirmed per inquiry." % agency,
                        "territory": "",
                        "credit": "",
                        "publish": "yes",
                        "cross_listed": "yes"
                        if r["title"].strip().lower() in cross
                        else "",
                    }
                )
        written[agency] = (out, len(mine))

    for agency, (out, n) in sorted(written.items()):
        print("wrote %s  (%d titles)" % (os.path.relpath(out, HERE), n))
    no_year = sum(1 for r in records if not r["year"])
    print("  %d titles with no year, %d with no runtime, %d with no logline"
          % (no_year, len(records), len(records)))
    print("  %d titles appear in both agency lists (imported twice, "
          "cross_listed=yes, not merged)" % len(cross))
    labels = sorted({r["genre"] for r in records if r["genre"]})
    print("  %d distinct genre labels carried over verbatim" % len(labels))


if __name__ == "__main__":
    main()
