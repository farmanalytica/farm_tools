(# MapBiomas — Features & Methodology

The MapBiomas page brings the **MapBiomas Brasil Collection 9** land-use /
land-cover archive into the plugin as an **in-module visualization** — the maps
are rendered to PNG thumbnails and browsed inside the dialog (year slider, class
legend, transition chart), mirroring the FARM web app. Raw classification and
transition rasters can also be exported to QGIS as styled layers on demand.

Coverage is **Brazil only**. The archive spans **1985–2023** at **30 m**
resolution; the Earth Engine asset is a single multi-band image whose bands are
`classification_1985 … classification_2023`, each band holding the MapBiomas
class ID per pixel for that year.

Code map:

| Layer | File | Responsibility |
|---|---|---|
| View | `view/mapbiomas.py` | Three-tab layout (Inputs / Coverage / Transition), widgets, per-section progress bars |
| Controller | `controllers/mapbiomas_ctrl.py` | UI orchestration, worker lifecycle, chart + slider logic |
| Service | `services/mapbiomas_service.py` | All Earth Engine logic (thumbnails, transition algorithm, GeoTIFF export) |
| Worker | `workers/mapbiomas_worker.py` | Runs the slow EE/network work off the UI thread |
| Chart render | `view/plotly_render.py` | Renders the per-year bar chart, live restyle on slider drag |
| GEE auth | `services/gee_service.py` | Earth Engine initialization (high-volume endpoint) |

---

## 0. Architecture & threading

**What it does.** The AOI is read from a QGIS vector layer (or a drawn box) and
converted to an `ee.FeatureCollection` on the **main thread** (QGIS layers are
not thread-safe). The slow Earth Engine + network work then runs inside a
`MapBiomasWorker` (`QThread`), which reports back via `finished` / `failed` /
`progress` signals.

**Methodology.**
- A single worker handles every product via a `mode` flag (`"coverage"`,
  `"transition"`, `"download"`, `"download_transition"`); the result is a plain
  dict the controller branches on.
- `ee` is imported lazily inside service methods so the dialog still opens before
  the `extlibs` dependency bundle is provisioned.
- Earth Engine is initialized against the **high-volume endpoint**
  (`earthengine-highvolume.googleapis.com`), which is built for many concurrent
  requests — the right fit for the parallel thumbnail fan-out below.

## 1. Data source & legend

**What it does.** The page reads the Collection 9 integration asset
`projects/mapbiomas-public/.../mapbiomas_collection90_integration_v1` and renders
it with the official MapBiomas palette and class scheme.

**Methodology.**
- The palette (`MAPBIOMAS_PALETTE`, class IDs 0–62) and Portuguese legend labels
  (`MAPBIOMAS_CLASS_LABELS`) are kept as **data**, not translated — they must
  match the published Collection 9 legend exactly.
- The Coverage tab shows the legend as colored ■-glyph swatch rows beside the
  year image (Qt rich text honors a colored glyph but not sized inline blocks).

## 2. Coverage (annual classification, in-module)

**What it does.** Renders every year (1985–2023) to a PNG thumbnail, then a year
slider swaps the displayed image. Each year is `getThumbURL`-rendered server-side
with the MapBiomas palette (`min=0, max=62`), clipped to the AOI.

**Methodology.**
- The AOI bounding box (`geometry().bounds()`) is the thumbnail region; the
  longest edge is fixed at **1024 px**.
- **Parallel download.** The 39 `getThumbURL` round-trips run **concurrently**,
  not one year at a time. Each blocking resolve + `requests.get` + write is
  offloaded with `asyncio.to_thread`, and a `Semaphore` caps the in-flight count
  (20). A single year failing is skipped, not fatal. PNG output is identical to
  the previous serial loop — only wall-clock improves.
- Progress is reported per completed year (`MapBiomas <year>  (done/total)`) in
  the Coverage section's own progress bar.
- Once loaded, the slider maps year → cached `QPixmap`; missing years snap to the
  nearest available year.

## 3. Single-year download to QGIS

**What it does.** Downloads one year's classification as a GeoTIFF and loads it
as a styled, queryable QGIS raster layer — without rendering every year first.

**Methodology.**
- Unlike the thumbnails, the GeoTIFF keeps the **raw class IDs** as pixel values
  (`getDownloadURL`, `scale=30`, `EPSG:4326`), so the layer can be queried and
  styled categorically.
- The controller applies a `QgsPalettedRasterRenderer` built from
  `MAPBIOMAS_CLASS_LABELS` + `MAPBIOMAS_PALETTE`, so the QGIS layer matches the
  in-module legend.
- This download can be triggered from the Inputs tab (year picker) or from the
  Coverage tab (current slider year).

## 4. Transition analysis (source → target)

**What it does.** Maps the **first year** each pixel transitioned from a *source*
class to a *target* class, and charts the converted area per year. Presets cover
Pasture→Crop, Deforestation, Forest regrowth, Agricultural expansion, and Urban
expansion; a custom class picker builds an arbitrary source → target set.

**Methodology — first-transition-year image.**
For each year `Y` in **1986–2023**:
- `was_source` = pixel belonged to a source class in `Y-1` (`remap` source IDs → 1, else 0).
- `became_target` = pixel belongs to a target class in `Y` (same remap).
- `flipped = was_source AND became_target` → the pixel transitioned in year `Y`.
- Each year's flipped mask is multiplied by `Y` and `selfMask`-ed.
- The per-year images are reduced with `ImageCollection(...).min()`, so each
  pixel keeps its **earliest** transition year; pixels that never transitioned
  stay masked.

**Methodology — converted-area statistics.**
- A `frequencyHistogram` reducer over the `first_year` band counts pixels per
  transition year. `maxPixels` uses agrigee_lite's `ee_get_number_of_pixels`
  (absolute cap) with `bestEffort=True`, so an oversized AOI is auto-coarsened by
  EE instead of failing with "Too many pixels"; farm-sized AOIs are unaffected.
- Pixel count → hectares via `30 × 30 / 10000 = 0.09 ha` per pixel.
- Output: `{total_hectares, per_year: [{year, hectares}, …]}`.

**Methodology — display.**
- The transition map is a PNG thumbnail of `first_year`, colored by year with a
  diverging blue→red palette (`min=1986, max=2023`).
- The per-year hectares are charted as a Plotly bar chart beside the map.

## 5. Year-range filter (live)

**What it does.** A two-handle range slider on the Transition tab narrows the
focus to a sub-window of transition years; **both** the bar chart and the
transition map update to that window.

**Methodology.**
- In-range bars keep their gradient color; out-of-range bars fade to grey, and
  the summary shows the in-range total hectares for the selected window.
- **Chart — instant.** Recoloring runs **client-side** via `Plotly.restyle`
  (JS, no page reload) on every slider tick; a debounced full redraw (~200 ms
  after the slider settles) is the authoritative fallback. The stored figure is
  kept in sync so "Open chart in browser" reflects the current range.
- **Map — on settle.** Re-coloring the map means a fresh server-side thumbnail,
  so it runs in its own worker once the slider settles (the chart's per-tick
  recolor stays instant). The map image is dimmed and the summary shows a
  `rendering map …` cue while it renders. Drags coalesce: only the latest
  window is rendered, and the color scale stays pinned to 1986–2023 so a year
  keeps the same color in every window.

## 6. Transition export to QGIS

**What it does.** Exports the `first_year` raster (pixel value = transition year,
masked elsewhere) as a QGIS layer, **limited to the selected year range**.

**Methodology.**
- When the slider window is narrower than the full span, pixels outside
  `[year_min, year_max]` are masked (`gte/lte` + `updateMask`) before
  `getDownloadURL`, so the exported layer matches what the chart shows.
- Pixel values are the transition years, so the layer is classed by year in
  QGIS. The paletted renderer lists **only the in-range years**, with colors
  pinned to the full-range gradient so each year matches the in-module map.

---

## Performance notes

- **Parallel coverage** — all 39 thumbnails fetch concurrently (asyncio +
  semaphore) instead of serially; the dominant cost was 39 sequential network
  round-trips.
- **High-volume endpoint** — Earth Engine is initialized against
  `earthengine-highvolume.googleapis.com`, raising throughput and easing rate
  limits under the parallel fan-out.
- **Histogram hardening** — `bestEffort=True` + an explicit pixel cap let large
  AOIs return approximate stats rather than erroring.
- **Live chart recolor** — slider drags restyle the existing chart client-side
  instead of rebuilding and reloading the page.

None of these change the end-user output (same PNGs, same stats, same exports) —
they only make the module faster and more responsive.
