# Brand masters

Source art. **Not published** — `build.py` only copies `site/assets/`.

| File | What it is |
|---|---|
| `logo-master.png` | 1024×1024 flat vault mark, transparent background. Master for everything on the site. |
| `logo-3d-master.jpg` | 1024×1024 glossy 3D render. White background, no alpha — kept for print/deck use. |

The site uses the **flat** master because it has a real alpha channel (so it
sits on the dark header cleanly) and stays legible when scaled down. The 3D
render is a JPEG, so it cannot carry transparency, and keying out its white
background also removes the near-white highlights along the top steel bevel.

Regenerating the published assets from the flat master:

```bash
cp brand/logo-master.png assets/logo-200.png && sips -Z 200 assets/logo-200.png
cp brand/logo-master.png /tmp/fav.png && sips -c 560 560 /tmp/fav.png
cp /tmp/fav.png assets/favicon-32.png  && sips -Z 32  assets/favicon-32.png
cp /tmp/fav.png assets/favicon-180.png && sips -Z 180 assets/favicon-180.png
```

The `-c 560 560` centre-crop drops the outer rivet ring, which turns to mush
below about 32px. Keep it if you re-cut the favicon.
