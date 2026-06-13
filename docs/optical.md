# Optical — Features & Methodology

The Optical page analyses the **Sentinel-2 Harmonized Surface Reflectance**
archive (`COPERNICUS/S2_SR_HARMONIZED`) through Google Earth Engine. The user
picks an AOI, a date range and a vegetation index; the page builds a **per-date
AOI-average index time series**, plots it in an interactive chart, and lets the
user filter, smooth, overlay climate, sample points/features, and export
imagery — RGB scenes, single-index rasters, and synthetic composites — to QGIS.

Unlike the legacy path, **filtering happens client-side after the run**: the
collection is fetched once with cloud / SCL-valid-pixel / coverage metadata on
every image, so the Results "Adjust filter" popup re-filters and re-plots the
cached series with no new Earth Engine call. Only changes that alter the pixels
feeding the index (the SCL mask, the date range) require a re-run.

Code map:

| Layer | File | Responsibility |
|---|---|---|
| View | `view/optical.py` | Three-tab layout (Intro / Inputs / Results), all `s2_*` widgets, segmented AOI/Points/Features plot toggle |
| Filter popup | `view/optical_filter_dialog.py` | Client-side cloud / valid-pixel / coverage threshold dialog (no GEE) |
| Index reference | `view/optical_index_info.py` | Combo order, per-index HTML descriptions/formulas, custom-band reference |
| Controller | `controllers/optical_ctrl.py` | UI orchestration, worker lifecycle, filtering, smoothing, plot/view switching, raster styling |
| Service | `services/optical_service.py` | All Earth Engine logic (time series, metadata, single-date/composite downloads) |
| Index registry | `tools/indexes.py` | 19 built-in index functions, custom-expression parse/validate/apply, custom-index JSON store |
| Worker (run) | `workers/optical_worker.py` | AOI time-series fetch off the UI thread |
| Worker (analysis) | `workers/optical_analysis_worker.py` | Point / per-feature series, streamed one geometry at a time |
| Worker (single) | `workers/optical_preview_worker.py` | One-date RGB or index GeoTIFF download |
| Worker (composite) | `workers/optical_composite_worker.py` | Synthetic index composite build + download |
| Worker (batch) | `workers/batch_download_worker.py` | Sequential per-date multispectral download with progress/cancel |
| GEE auth | `services/gee_service.py` | Earth Engine initialization (high-volume endpoint) |

---

## 0. Architecture & threading

**What it does.** The AOI is read from a QGIS vector layer (or a drawn box) and
converted to an `ee.FeatureCollection` on the **main thread** (QGIS layers are
not thread-safe), then the slow Earth Engine + network work runs in dedicated
`QThread` workers reporting back via `finished` / `failed` (and `series_ready`
/ `progress`) signals.

**Methodology.**
- One worker class per job kind rather than a single mode flag:
  `OpticalWorker` (AOI series), `OpticalAnalysisWorker` (points/features),
  `OpticalPreviewWorker` (single-date image), `OpticalCompositeWorker`
  (composite), `BatchDownloadWorker` (per-date multispectral), plus the shared
  `ClimateWorker`. The controller owns each worker handle, disables its button
  while running, and `deleteLater`s it on completion.
- `ee` is imported lazily where possible; the service module imports it at top
  level, so the run is gated on `gee_service.is_authenticated` (the controller
  pops an "authenticate on the Auth page" warning otherwise).
- Earth Engine is initialized against the **high-volume endpoint**
  (`earthengine-highvolume.googleapis.com`, `gee_service.py`).
- A run captures the SCL settings (`apply_scl`, the invalid-class list) and the
  date range at launch and **replays them** for the composite and the
  point/feature analysis, so every derived product matches the masking behind
  the plotted series.

## 1. Data source & vegetation indices

**What it does.** Reads `COPERNICUS/S2_SR_HARMONIZED`, computes one vegetation
index per image, and exposes **19 built-in indices** plus a custom-expression
builder.

**Methodology.**
- `INDEX_ORDER` / `VEGETATION_INDICES` (`optical_index_info.py`) hold the combo
  order and the HTML description + formula shown in the Inputs explanation
  panel; `INDEX_REGISTRY` (`tools/indexes.py`) maps each name to the EE function
  that produces a single `"index"` band (NDVI, GNDVI, EVI, EVI2, SAVI, MSAVI,
  SFDVI, CIgreen, NDRE, ARVI, NDMI, NBR, SIPI, NDWI, ReCI, MTCI, MCARI, VARI,
  TVI).
- Normalized-difference indices use `image.normalizedDifference([...])` on raw
  DN; expression-based indices divide bands by **10000** first to work in
  0–1 reflectance (SAVI fixes `L = 0.5`). The 19 index dropdowns (Inputs,
  single-date VI, composite) are kept in sync by `update_index_combobox`.
- **Custom indices.** `validate_custom` rejects empty/reserved/duplicate names
  and validates the expression: only the 12 band tokens (`B1`…`B12`, `B8A`)
  and arithmetic/grouping chars are allowed, and the band-substituted form must
  `ast.parse` cleanly. `apply_custom` evaluates the expression via
  `image.expression(...)` with each band divided by 10000. Saved expressions
  persist to `tools/custom_index.json`; only the Inputs combo carries the
  `Custom…` builder entry.

## 2. AOI time series (the run)

**What it does.** For the chosen AOI, date range and index, builds a row per
acquisition date holding the AOI-average index value plus cloud / valid-pixel /
coverage metadata, and plots the series in the Results web view.

**Methodology — collection build.**
- `_build_base_collection` filters `COPERNICUS/S2_SR_HARMONIZED` by AOI bounds
  and date.
- `_keep_one_image_per_date` keeps **one image per acquisition date**. Each
  image is scored by AOI footprint coverage (`image.geometry().intersection`
  ÷ AOI area, ×1000) minus normalized cloud cover (`CLOUDY_PIXEL_PERCENTAGE`
  ÷ 100) — coverage dominates, low cloud breaks ties — then sorted descending
  and `distinct("date")`-ed. Scoring uses cheap geometry/metadata only, so the
  expensive per-image statistics are computed for the kept images alone.

**Methodology — per-image metadata.**
- `cloud_pct` = `CLOUDY_PIXEL_PERCENTAGE` (whole-tile cloudiness from metadata).
- `coverage_pct` = AOI ∩ image-footprint area ÷ AOI area ×100. This uses the
  Sentinel-2 nominal MGRS tile square, so single-tile AOIs read ~100% even
  under partial swath — it only catches AOIs spanning multiple granules.
- `valid_pixel_pct` = SCL-valid pixels ÷ total pixels ×100, both via a 10 m
  `reduceRegion(count)` over the AOI. "Valid" means **not** in the checked SCL
  classes (`_build_valid_scl_mask`). This is the local, in-AOI clear-pixel
  measure.
- `AOI_average` = 10 m `reduceRegion(mean)` of the `"index"` band over the AOI.
- Rows are pulled in one `getInfo()` on a `FeatureCollection` of the per-image
  properties; rows with a null `AOI_average` are dropped. The controller frames
  them into a DataFrame with columns
  `date, AOI_average, cloud_pct, valid_pixel_pct, coverage_pct, image_id`.

## 3. SCL cloud mask (run-time)

**What it does.** A 12-class Scene Classification Layer checklist on the Inputs
tab selects which SCL classes are treated as invalid; cloud / shadow / defect
classes are checked by default.

**Methodology.**
- The checked classes (`_SCL_CLASSES`, 0–11) **always** define the valid-pixel
  count used by the Results filter, regardless of the mask toggle.
- When "Apply SCL mask" is on, `_apply_scl_mask` additionally `updateMask`s
  those classes out of every image **before** the index is computed, so they
  affect the time series and every downloaded raster. Because masking changes
  the pixels, it lives on the Inputs tab (applied at run time) — not in the
  client-side filter popup.

## 4. Client-side filtering & date selection

**What it does.** The "Adjust filter" popup narrows the cached series by three
thresholds; "Filter dates" toggles individual dates in/out. Both re-plot
instantly without contacting Earth Engine.

**Methodology.**
- Thresholds (`DEFAULT_FILTER_SETTINGS`: cloud ≤ 40, valid pixels ≥ 80,
  coverage ≥ 90) feed `_filter_mask`, a pandas boolean over the cached
  DataFrame. The popup shows a live "N images match" count via `count_matching`
  while the sliders move, and only applies on **OK**.
- `_filtered_dataframe` is the single source of truth for every downstream
  action (plot, CSV, batch, composite, single-date dropdown): it applies the
  thresholds, then the optional manual date set. Applying new thresholds
  overrides any manual date selection and rebuilds the single-image date combo.

## 5. Time-series plot, smoothing & climate overlay

**What it does.** Renders the AOI-average series as an interactive Plotly chart;
optionally overlays a Savitzky-Golay smoothed line and NASA POWER precipitation
bars. "Open in Browser" and "Export CSV" act on the current filtered view.

**Methodology.**
- The chart HTML (`view/sar_plot.render_chart_html`) is written to a temp file
  and loaded into `s2_web_view`; the previous temp file is removed on re-render.
- **Smoothing** is a view-only transform: `_smoothed_series` runs
  `scipy.signal.savgol_filter` on the filtered, date-sorted series, clamping the
  window odd and ≤ series length and the polyorder below the window. It
  re-renders only — no GEE call.
- **Climate overlay.** `ClimateWorker` fetches NASA POWER over the same date
  range and AOI; `_precip_bars` aggregates monthly precipitation
  (`NasaPowerService.monthly_precipitation`) placed mid-month against the daily
  axis. A fresh run invalidates any prior overlay. CSV export appends the
  smoothed column and any captured point/feature series as extra columns aligned
  on date; climate has its own CSV export (precip + temperature).

## 6. Point & per-feature analysis

**What it does.** A click-to-sample point tool extracts an index series per
clicked map point; "Plot per-feature series" extracts one series per polygon
feature of the AOI layer, keyed by an attribute field. Series render as a
multi-line chart against the AOI average reference line, switched via the
AOI / Points / Features segmented toggle.

**Methodology.**
- Both reuse the run's captured params (date range, index, SCL settings, custom
  expression) so the curves stay comparable to the AOI curve.
  `get_geometry_time_series` mirrors the AOI processing but dedups by **lowest
  cloud cover only** (the coverage rule divides by AOI area, which is zero for a
  point).
- Points use `ee.Reducer.first()` — the exact 10 m pixel under the click, truer
  than averaging a buffered disc; features use `ee.Reducer.mean()` over the
  polygon. Feature geometry is made valid, reprojected to EPSG:4326 and stripped
  of Z before becoming an EE geometry; labels come from the chosen ID field,
  de-duplicated.
- `OpticalAnalysisWorker` streams **one geometry result at a time** via
  `series_ready`, so each clicked point's line appears as it lands; features
  render once as a batch on `finished`. Rapid point clicks queue behind the
  running worker and flush on completion. The AOI average is drawn as a grey
  reference line under every multi-series chart.

## 7. Single-date image (RGB / index)

**What it does.** For the date selected in the Results combo, previews
(temp dir) or downloads (download folder) either a multispectral RGB composite
or a single-band vegetation-index raster, loaded into QGIS styled.

**Methodology.**
- Both fetch the same one-scene-per-date pick as the time series, clipped to the
  AOI plus the buffer (§9), via `getDownloadURL` (`scale=10`, GeoTIFF,
  EPSG:4326), downloaded with `requests` (300 s timeout) to a `_unique_path`.
- **RGB:** the raw 12-band SR stack (`_MULTISPECTRAL_BANDS`, B10 absent) with
  GDAL band descriptions set. Loaded via `QgsMultiBandColorRenderer` under one
  of five band presets (`_RGB_MODE_BANDS` — true color B4/B3/B2 default,
  plus NIR / SWIR false-color combos) with a per-band 2–98% cumulative-cut
  stretch.
- **Index:** the single `"index"` band, loaded as a pseudocolor raster with the
  chosen color ramp (`RdYlGn` default).

## 8. Synthetic composite

**What it does.** Reduces the index across **only the dates still shown on the
plot** into one composite image, by a chosen metric, previewed or downloaded.

**Methodology.**
- `build_index_composite` rebuilds the one-scene-per-date collection over the
  date span, then `Filter.inList("date", ...)` keeps exactly the filtered dates,
  re-applying the run's SCL masking so the composite matches the plotted values.
- Metrics (`_aggregate_index_collection`): Mean, Median, Min, Max, Amplitude
  (max−min), Standard Deviation, Sum. The reducer output is re-aligned to the
  first image's projection (`setDefaultProjection`) and geometry — without this
  the result defaults to a 1° projection and downloads misaligned/blank.
- **Area Under Curve** (`_calculate_auc`) integrates the index over time by the
  trapezoidal rule: per-date timestamps become day offsets, consecutive index
  values are summed × interval ÷ 2 over an array image, masked to pixels valid
  in every date, and re-anchored to the first image's footprint.
- The result is cast to float, masked to the exact AOI (the GeoTIFF region stays
  rectangular), clipped to the buffered region, renamed `"index"`, and
  downloaded as above. Loaded as a pseudocolor raster named by index + metric.

## 9. Batch download & download buffer

**What it does.** "Batch Download (All Dates)" pulls the raw multispectral scene
of every filtered date into QGIS as RGB layers; a buffer slider grows/crops the
download region of every optical output.

**Methodology.**
- `BatchDownloadWorker` is a generic sequential worker driven by an injected
  `download_one(date)` callable (`OpticalService.download_multispectral_for_date`);
  it emits per-date progress to a modal `QProgressDialog`, supports cancel
  (mutex-guarded flag checked between dates), and a single date failing is
  skipped, not fatal. Completed scenes load as true-color RGB layers.
- The **buffer** (`s2_buffer_slider`, ±300 m, with a ±3 m dead-zone) feeds
  `_download_region`: positive grows the AOI geometry (`buffer(+m)`), negative
  crops the edges. It applies to every downloaded/previewed output (single date,
  batch, composite) but not to the plotted statistics.

---

## Performance notes

- **Fetch once, filter client-side** — the collection carries cloud / SCL /
  coverage metadata per image, so threshold and date filtering, smoothing and
  view switching re-plot from the cached DataFrame with no new GEE request.
- **Dedup before stats** — `_keep_one_image_per_date` scores images with cheap
  geometry/metadata and keeps one per date, so the expensive 10 m
  `reduceRegion` statistics run on the kept images only.
- **Streamed point series** — `OpticalAnalysisWorker` emits each geometry's
  series as it finishes, so clicked points appear incrementally instead of after
  the whole batch; rapid clicks queue rather than spawn parallel workers.
- **High-volume endpoint** — Earth Engine is initialized against
  `earthengine-highvolume.googleapis.com`.
- **Off-thread I/O** — every slow EE/network call runs in a `QThread`, keeping
  QGIS responsive (the legacy point path ran on the main thread behind a wait
  cursor).
