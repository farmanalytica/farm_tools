# FARM tools website

Vue 3 + Vite website for the [FARM tools](https://github.com/farmanalytica/farm_tools)
QGIS plugin, supported by [FARM Analytica](https://farmanalytica.com.br).

Languages: **en-US** and **pt-BR** (toggle in the header, persisted in localStorage,
auto-detected from the browser).

## Pages

| Route | Content |
|---|---|
| `/` | Landing page: hero, intro video, modules, workflow, GEE setup, resources, about |
| `/tutorials` | YouTube video tutorials grouped by category. Videos with no published ID render a "coming soon" placeholder |
| `/wiki/:slug` | Written documentation per module (getting started, Optical, Landsat, SAR, DEM, SYSI, ClimaPlots, Field Guide, exports, FAQ) |

## Development

```bash
npm install
npm run dev      # local dev server
npm run build    # production build → dist/
npm run preview  # serve the production build
```

## Adding a tutorial video

Videos are hosted on YouTube. Edit `src/data/videos.js` and set the `youtubeId`
of the matching entry (currently `null` for placeholders). Titles and
descriptions carry both locales inline.

## Editing wiki content

Articles live in `src/wiki/articles.en-US.js` and `src/wiki/articles.pt-BR.js`
(one entry per slug, kept in the same order in both files). Section types:
`h2`, `p`, `list`, `steps`, `table`, `note`.

## UI strings

Interface translations live in `src/i18n/en-US.js` and `src/i18n/pt-BR.js`.

## Deployment

`vite.config.js` uses `base: './'` and the router uses hash history, so the
build works on GitHub Pages (project site or custom domain) without extra
configuration — publish the `dist/` folder.
