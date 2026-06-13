# DEM — Features & Methodology

The DEM page (**EasyDEM** in the UI) downloads ready-to-use terrain elevation
models for an area of interest and loads them straight into QGIS as styled
raster layers. The user picks a polygon AOI (or draws a box), the page filters a
catalog of ~30 elevation datasets down to those that actually cover the AOI,
the chosen dataset is clipped to the AOI on the Earth Engine side, downloaded as
a GeoTIFF, and added to the map with a Magma pseudocolor ramp.

The catalog spans global products (Copernicus GLO-30, SRTM, NASADEM, ASTER,
ALOS, MERIT, GMTED2010, ETOPO1, …) and high-resolution regional/national sets
(Netherlands AHN2–4 at 0.5 m, USGS 3DEP 1 m, England/France 1 m, ArcticDEM and
REMA at 2–8 m, Australia 5 m, …). Resolutions range from **0.5 m to 1800 m**.
The module **does not** compute derived terrain products (slope, hillshade,
contours) — it delivers the raw elevation raster; derivation is left to QGIS.

Code map:

| Layer | File | Responsibility |
|---|---|---|
| View | `view/download_dem.py` | AOI/dataset page: layer picker, draw-AOI + hybrid buttons, dataset combo, info browser, buffer slider, download button |
| Controller | `controllers/dem_ctrl.py` | UI orchestration, AOI capture, worker lifecycle, combo population, layer zoom/debounce |
| Catalog/registry | `services/dem_registry.py` | Loads `dem_catalog.json`, builds the dataset image, AOI coverage checks |
| Catalog data | `assets/dem_catalog.json` | The dataset list (name, EE collection, band, resolution, coverage bbox, HTML info) |
| Download service | `services/dem_service.py` | Clip to AOI + `getDownloadURL` GeoTIFF fetch and disk write |
| Workers | `workers/dem_worker.py` | Off-thread coverage check (`DatasetAvailabilityWorker`) and download (`DemDownloadWorker`) |
| Renderer | `renderers/dem_renderer.py` | Loads the GeoTIFF as a Magma single-band pseudocolor layer |
| Render utils | `renderers/raster_renderer_utils.py` | Generic pseudocolor renderer + layer-tree insertion |
| Info panel | `managers/dataset_manager.py` | Pushes the selected dataset's HTML metadata into the info browser |
| AOI → EE | `services/aoi_service.py` | Dissolves the polygon layer to a 2D EPSG:4326 `ee.FeatureCollection` + bbox |

---

## 0. Architecture & threading

**What it does.** The AOI is read from a QGIS polygon layer (or a drawn box) and
converted to an `ee.FeatureCollection` on the **main thread** (QGIS layers are
not thread-safe). The two slow, network-bound steps — checking which datasets
cover the AOI and downloading the DEM — each run in their own `QThread`, which
reports back via `finished` / `failed` signals.

**Methodology.**
- `DEMCtrl` owns both workers (`_dataset_worker`, `_dem_worker`) and guards
  re-entry: a new download is ignored while one is still running
  (`isRunning()`), and finished workers are `deleteLater`-d.
- `AOIService.get_ee_feature_colection_from_layer` validates the layer is a
  polygon, dissolves all (or only selected) features via `unaryUnion`,
  `makeValid`s invalid geometry, reprojects to EPSG:4326, strips Z, and returns
  both the `ee.FeatureCollection` and its bounding box `[minx, miny, maxx, maxy]`.
  The bbox is cached so coverage checks can skip the EE round-trip when the
  catalog's static coverage box already rules a dataset out.
- Layer selection is **debounced** (300 ms `QTimer`): rapid `layerChanged`
  events collapse to one AOI capture + catalog refresh, and on each change the
  canvas zooms to the layer extent (transformed to the canvas CRS, scaled ×1.8).
- Loading the downloaded GeoTIFF into QGIS happens back on the main thread, in
  the controller's `finished` handler — the worker only fetches bytes.

## 1. Dataset catalog & registry

**What it does.** A JSON catalog defines every selectable DEM; `DEMRegistry`
loads it and resolves each entry to an `ee.Image`.

**Methodology.**
- `assets/dem_catalog.json` is read with `utf-8-sig` (tolerates a BOM) into
  `DEMDataset` objects keyed by display name. Each entry carries the EE
  `collection`, elevation `band`, `resolution`, `is_collection` /`is_global`
  flags, an optional `coverage_bbox`, and an HTML `info` blurb with a source
  link.
- `get_dataset_image` resolves the entry to a single band: an
  `ImageCollection(...).select(band).mosaic()` when `is_collection` is true
  (e.g. 3DEP tiles, ALOS, AHN3/4), otherwise a plain `Image(...).select(band)`
  (e.g. SRTM, NASADEM, Copernicus single-image assets).
- Band names vary per source and are stored as data, not inferred — `DEM`,
  `elevation`, `dtm`, `DSM`, `MNT`, `be75`, `bedrock`, `b1`, etc.

## 2. AOI coverage filtering

**What it does.** When an AOI is set, only datasets that actually overlap it are
offered in the combo; everything else is hidden.

**Methodology — two-stage check (`DEMRegistry.has_coverage`).**
- **Stage 1 — static bbox reject (free).** If the dataset declares a
  `coverage_bbox`, it is tested against the AOI bbox with a plain rectangle
  intersection (`check_bbox_intersects`). A non-overlapping regional dataset
  (e.g. AHN over a Brazilian AOI) is dropped immediately, with no EE call.
- **Stage 2 — live EE presence check.** For survivors:
  - `is_collection` datasets → `ImageCollection(...).filterBounds(geometry).size().getInfo() > 0`
    (does any tile intersect the AOI?).
  - single-image datasets → a `reduceRegion` with `Reducer.count()` at
    `scale=1000`, `maxPixels=1e6`; the band's count must be `> 0`.
  - any EE error in this stage is swallowed and treated as "no coverage"
    (`except Exception: return False`), so one bad asset never aborts the scan.
- The scan runs inside `DatasetAvailabilityWorker`; while it runs the combo
  shows a disabled "Checking available datasets…" placeholder. On success the
  combo is repopulated with the covering names; on failure it is re-enabled
  empty. A passive "EE not initialized" error (unauthenticated) is suppressed.
- **Unauthenticated fallback.** If GEE isn't authenticated, the controller skips
  coverage checks entirely and lists the **full** catalog
  (`load_available_datasets`), so the page is still browsable before login.
- `managers/dataset_manager.py` holds an equivalent **synchronous** scan
  (wait-cursor + `processEvents`) used elsewhere; the controller's own path is
  the threaded one.

## 3. Dataset info panel

**What it does.** Selecting a dataset shows its resolution, coverage, provenance
paragraph, and a source link.

**Methodology.**
- `on_dataset_changed` → `DatasetManager.update_dataset_info` pulls the
  `DEMDataset.info` HTML straight from the catalog entry and sets it on the
  `QTextBrowser` (`setHtml`); the browser opens external links in the system
  browser. Empty selection clears the panel.

## 4. AOI buffer

**What it does.** A slider widens or shrinks the download footprint from
**−300 m to +300 m** before the DEM is clipped.

**Methodology.**
- `_apply_buffer` is a no-op at 0; otherwise it maps each AOI feature to
  `feature.buffer(distance).bounds()` — i.e. the buffered geometry is reduced to
  its bounding box, so the download region is always a rectangle. Positive values
  pull in surrounding terrain; negative values crop the edges.
- The slider snaps to 0 inside a ±3 m dead-zone and labels the live value
  ("Buffer: +120 m"). The buffer is applied to the AOI only at download time, not
  during coverage checks.

## 5. Download to QGIS

**What it does.** Downloads the selected dataset, clipped to the (buffered) AOI,
as a GeoTIFF and loads it as a styled raster layer.

**Methodology — clip + fetch (`DEMService.download_dem`).**
- The dataset image is cast to float (`toFloat()`) and masked to the AOI: a
  `ee.Image(1).clip(geometry).mask()` is built and applied with `updateMask`, so
  pixels outside the AOI become transparent/no-data rather than a rectangular
  block of values.
- A `getDownloadURL` is requested with `scale=30`, the AOI bounds as `region`,
  and `format="GeoTIFF"`. **Note:** the export scale is fixed at 30 m regardless
  of the dataset's native resolution — sub-30 m sources (AHN, 3DEP 1 m, ArcticDEM)
  are resampled down to 30 m on export, and coarser sources keep their grid.
- The URL is fetched with `requests.get(timeout=300)`; a non-OK response raises
  `RuntimeError` with the HTTP status. The bytes are written to disk.
- **Output path.** Filename is `FARM_tools_<dataset>.tif` (spaces → `_`,
  `/` → `-`). Target dir is the user-picked download folder if it exists,
  otherwise the system temp dir. `_get_unique_path` appends `_1`, `_2`, … to
  avoid clobbering an existing file.

**Methodology — load + style.**
- `DEMRenderer.load_dem_to_qgis` → `RasterRendererUtils.load_pseudocolor_raster`
  loads the GeoTIFF, reads band-1 min/max from `bandStatistics`, and builds a
  256-stop **interpolated** `QgsColorRampShader` over the **Magma** ramp wrapped
  in a `QgsSingleBandPseudoColorRenderer`. The layer is inserted at the **top**
  of the layer tree and repainted. A failed load raises `RuntimeError`.
- The download button is gated: it warns (instead of running) when GEE is
  unauthenticated, when no AOI is selected, or when no dataset is chosen, and it
  shows a "Downloading…" busy state (disabled button) until the worker returns.

## 6. Basemap & AOI drawing helpers

**What it does.** The page can add a Google Hybrid basemap and let the user draw
a rectangular AOI directly on the canvas instead of picking a layer.

**Methodology.**
- "Add Google Hybrid Layer" calls `add_google_hybrid_layer` and pushes a message
  bar confirmation.
- "Draw AOI" toggles a canvas map tool (`start_draw_aoi`): clicking again while
  the tool is active unsets it. The drawn box feeds the same `layer_combo` path
  the rest of the workflow consumes (Shift = square, Esc = cancel, per the
  button tooltip).

---

## Performance notes

- **Off-thread network work** — both the catalog coverage scan and the DEM
  download run in `QThread` workers, so the dialog stays responsive during EE
  round-trips and the GeoTIFF fetch.
- **Free pre-filter** — the static `coverage_bbox` intersection rejects
  out-of-region datasets before any Earth Engine call, so the live presence
  check (`filterBounds`/`reduceRegion`) only runs on plausibly-covering sets.
- **Debounced AOI capture** — rapid layer changes collapse to a single AOI
  conversion + catalog refresh via a 300 ms timer.
- **Bounded coverage probe** — the single-image presence check uses a coarse
  `scale=1000` / `maxPixels=1e6` `reduceRegion`, keeping the yes/no answer cheap
  regardless of AOI size.
