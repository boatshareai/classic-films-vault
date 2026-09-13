# Classic Films Vault — licensing site

A static catalog-and-contact site for the Classic Films Vault library.
165 titles, one page per title, searchable/filterable browse table,
and a licensing inquiry form that sends two emails.

No backend, no database, no video hosting, no user accounts.

**Live:** <https://boatshareai.github.io/classic-films-vault/>

Every push to `main` rebuilds and redeploys via
`.github/workflows/deploy.yml` — so updating the catalog is: edit
`data/catalog.csv`, commit, push. You can do that in the GitHub web editor
without cloning anything.

> The inquiry form is not connected yet. GitHub Pages is static-only, so the
> serverless handler in `functions/` has nowhere to run there. See
> **Connecting the inquiry form** below — Option B (a form-to-email service)
> works on Pages as-is; Option A needs a host with functions, such as
> Cloudflare Pages.

---

## Quick start

```bash
python3 build.py && python3 -m http.server -d dist 8000
```

Then open <http://localhost:8000>. That's the whole toolchain — Python 3
standard library only. No `npm install`, no build framework.

---

## Updating the catalog

`data/catalog.csv` is the source of truth. Edit it in Excel, Numbers, Google
Sheets, or any text editor, then rebuild:

```bash
python3 build.py
```

### Columns

| Column | Notes |
|---|---|
| `slug` | URL for the film's page (`films/<slug>.html`). Must be unique. Keep it stable once a link is public. |
| `title` | Display title. |
| `year` | 4-digit year. Leave blank if genuinely unknown. |
| `decade` | e.g. `1940s`. Drives the decade filter — keep it consistent with `year`. |
| `genres` | Semicolon-separated, e.g. `Western; Musical`. Each becomes a filter option. |
| `language` | Original language. Blank shows as "Not specified". |
| `runtime` | Minutes, digits only. Blank shows as "Not listed". |
| `logline` | Full synopsis. Truncated to one line in the table; shown in full on the film page. |
| `status` | `Available` or `Licensed` — controls the badge. |
| `licence_note` | Sentence shown in the Licensing box on the film page. |
| `territory` | Territory of an existing licence. Shown only when `status` is `Licensed`. |
| `credit` | Optional note, e.g. `Directed by John Ford`. |
| `publish` | `yes` to include the title on the site, `no` to hold it back without deleting the row. Blank counts as `yes`. |

Every current row is `publish=yes`; the column is there for when you need to
pull a title off the site temporarily without losing its data.

Adding a new genre, language, or decade needs no code change — the filter
options are generated from whatever is in the CSV.

### Regenerating from the spreadsheets

`data/catalog.csv` was generated from the two source workbooks in the parent
folder:

```bash
python3 etl.py     # overwrites data/catalog.csv
```

`etl.py` merges `ClassicFilms_Usable4YouTube.xlsx` (70 titles under the VA
Media non-exclusive YouTube licence → `Licensed`) with
`2024-01-04.KR-Avails (2).xlsx` (106 titles with no current licence →
`Available`), matching the 10 titles that appear in both, and dropping rows
whose synopsis field holds an internal research note rather than buyer-facing
copy. It reruns from scratch each time, so **any hand-edits to `catalog.csv`
will be lost.** Once you start editing the CSV directly, treat `etl.py` as a
one-time import.

The two source spreadsheets stay in the parent folder and are deliberately
outside this repo.

---

## Connecting the inquiry form

Out of the box the form validates input and then shows a "not connected yet"
notice — it never silently drops an inquiry. Pick one of these two options.

### Option A — serverless function (recommended)

This is the only option that produces the exact personalised auto-reply
("Hi *Name*, thanks for reaching out about *titles*…").

`functions/inquiry.js` is a standard `fetch` handler. It sends the internal
notification first, then the auto-reply, and reports success as long as the
notification went out — a bounced auto-reply never costs you the lead.

**Cloudflare Pages** (simplest):

1. Move the file to `dist/functions/api/inquiry.js` — or set your build
   command to `python3 build.py && mkdir -p dist/functions/api && cp
   functions/inquiry.js dist/functions/api/`.
2. In the Cloudflare dashboard, add environment variables:
   - `RESEND_API_KEY` — from your transactional email provider
   - `FROM_EMAIL` — a verified sender, e.g. `licensing@yourdomain.com`
   - `NOTIFY_TO` — the inbox that should receive inquiries
3. Set `ENDPOINT: "/api/inquiry"` in `assets/config.js`.

**Netlify or Vercel:** same environment variables; wrap the export in their
adapter (Netlify: `export default handler.fetch`; Vercel Edge: `export const
POST = (req) => handler.fetch(req, process.env)`).

The function is written against [Resend](https://resend.com)'s API because
it's a two-field setup. Any provider with an HTTP send endpoint works —
change the URL and body shape in `sendEmail()`.

> You'll need to create the email account and API key yourself; they're
> credentials, so they're not committed here and there's no placeholder key
> to accidentally ship.

### Option B — form-to-email service (no deploy step)

Works with Web3Forms, FormSubmit, Formspree, or similar:

1. Sign up and get your access key / endpoint.
2. In `assets/config.js`:
   ```js
   ENDPOINT: "https://api.web3forms.com/submit",
   MODE: "service",
   ACCESS_KEY: "your-key-here",
   NOTIFY_TO: "licensing@yourdomain.com",
   ```

The internal notification arrives with every field. **Caveat:** these
services send a *fixed* auto-reply body, so the reply won't include the
inquirer's name or their titles of interest. If that wording matters, use
Option A.

### Email copy

Both emails are defined in `functions/inquiry.js`.

- **To the inquirer** — subject: `We received your Classic Films Vault inquiry`
- **To you** — subject: `New licensing inquiry — <Company>`, body listing
  Name, Company, Email, Titles of interest, Intended use, Estimated volume,
  Message. `Reply-To` is set to the inquirer, so hitting reply just works.

---

## Deploying

`dist/` is a plain static folder. Drop it on Cloudflare Pages, Netlify,
GitHub Pages, S3, or any web host.

- **Build command:** `python3 build.py`
- **Publish directory:** `dist`

The whole site is ~1.3 MB including all 165 film pages. There are no external
requests — no CDN, no web fonts, no analytics, no trackers — so it loads fast
and needs no cookie banner as shipped. Any single page pulls one 18 KB
stylesheet and one 20 KB logo, both cached across the whole site.

---

## Layout

```
site/
├── build.py             static site generator (stdlib only)
├── etl.py               one-time spreadsheet → CSV import
├── data/catalog.csv     ← the catalog. Edit this.
├── assets/
│   ├── site.css         all styles
│   ├── catalog.js       browse page: search, filter, sort
│   ├── inquiry.js       form validation, prefill, submit
│   ├── carousel.js      home-page featured-titles carousel
│   └── config.js        ← your form endpoint goes here
├── functions/inquiry.js serverless email handler
├── brand/               logo masters — NOT published, see brand/README.md
└── dist/                generated output — don't edit, it's rebuilt
```

`dist/` is regenerated from scratch on every build, so never edit it
directly.

## Brand and palette

Steel-and-brass, taken from the vault logo. Every colour is a CSS custom
property at the top of `assets/site.css` — change them there and the whole
site follows.

| Token | Value | Role |
|---|---|---|
| `--steel-dk` | `#1A1A1A` | Header, hero, footer, table head |
| `--steel-mid` | `#2E2D2B` | Top of the hero gradient |
| `--steel` | `#242322` | Body text on light |
| `--light` | `#E8E6E1` | Page background (warm gray, never white) |
| `--light-2` | `#F1EFE8` | Cards, table surface, text on dark |
| `--brass` | `#C9A15C` | The single accent — buttons, rules, accents on dark |
| `--brass-ink` | `#7F6025` | Same hue darkened, for links and small text **on light** |
| `--gray` | `#6B6862` | Borders, dividers, muted text |

Two notes on why there are more tokens than the four base colours:

- **`--brass-ink` exists for contrast, not variety.** `#C9A15C` on `#E8E6E1`
  is about 1.9:1 — well under the 4.5:1 minimum for body text, and every film
  title in the catalog is a link. `--brass-ink` is the same hue darkened until
  it passes (4.67:1). Brass proper is still the accent everywhere it sits on
  steel or fills a button.
- **Form errors keep a red** (`#8F3323`). It's a functional signal rather than
  decoration, so it stays distinguishable from the accent; it's desaturated to
  sit inside the palette. Success and warning notices are brass and steel.

Status badges use the one accent: **Available** is brass, **Licensed** is
steel gray. The film-page hero is dark, so it overrides both with light-on-
dark variants (`.film-head .badge-*`).

All 24 foreground/background pairs on the site meet WCAG AA.

### Logo

`assets/logo-200.png` is the header mark, `assets/favicon-32.png` and
`favicon-180.png` the icons. All three are cut from `brand/logo-master.png` —
see `brand/README.md` for the regeneration commands and why the favicon is
centre-cropped.

## Featured titles

The home-page carousel sits directly below the hero — the "165 titles" claim
lands harder when the next thing you see is actual marquee titles.

Edit the `FEATURED` list at the top of `build.py` to change what appears.
Titles are matched against `data/catalog.csv` by name, and **the build fails
loudly** if one stops resolving — so renaming or unpublishing a film in the
CSV can't silently leave an empty card.

There is no key art for these films, so each card uses a typographic
placeholder in the brand's own idiom: a clapperboard stripe, the title's
initial ghosted in brass, and the licensing status. Dropping in real posters
later means replacing the `.poster` contents in `build_featured()` with an
`<img>` — the card, carousel, and layout don't change.

The track is a native scroll-snap scroller, so touch swipe and keyboard
scrolling work even if `carousel.js` never loads; the script only adds the
arrow buttons and their disabled states. Nothing autoplays.

## Notes on behaviour

- **Deep links.** `catalog.html?genre=Western`, `?decade=1940s`,
  `?status=Licensed`, `?q=holmes`, and `?intl=1` all pre-apply filters. The
  home page tiles and the film-page genre tags use them.
- **Prefill.** "Inquire about this title" links to
  `licensing.html?title=<film>`, which fills the Titles of interest field and
  tells the visitor it did.
- **Licensed titles are surfaced, not hidden.** They carry a badge in the
  table, on the film page, and in the filter, and the film page states the
  existing licence and its territory.
- **Mobile.** Under 620px the catalog table becomes stacked labelled cards
  rather than a horizontally scrolling table.
- **Accessibility.** Single `h1` per page, labelled form controls, inline
  validation messages tied to their fields, `aria-live` result count,
  sortable columns as real buttons with `aria-sort`, visible focus rings, and
  a skip link.
