# RepoLens — landing page

A self-contained static marketing site for RepoLens. No build step, no dependencies —
just `index.html`, `styles.css`, and `script.js`.

Design: an Indian-manuscript palette (parchment + ink + jewel tones), Indian-foundry
typefaces (Rozha One display, Mukta text, Spline Sans Mono for code), and restrained
rangoli / jaali motifs.

## Preview locally

```bash
cd website
python -m http.server 4000
# open http://localhost:4000
```

(Any static server works — `npx serve`, etc. Opening `index.html` directly works too,
though the clipboard copy needs a `http://` origin.)

## Deploy on GitHub Pages

This folder is published by `.github/workflows/pages.yml`. One-time setup:

1. In the repo: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
2. Push any change under `website/` (or run the **Deploy website** workflow manually).
3. The site goes live at `https://sumanthd032.github.io/RepoLens/`.

## Want it in its own repo instead?

Copy this folder's contents to the root of a new repo and either:

- enable Pages → *Deploy from a branch* → `main` / root (no workflow needed), or
- keep the `pages.yml` workflow but change `path: website` to `path: .`.

All asset links are relative, so the site works at any base path without changes.
