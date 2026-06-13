# SAR — Features & Methodology

The SAR page brings **Sentinel-1 C-band radar** into the plugin as an
Earth Engine workflow: it builds an analysis-ready Sentinel-1 image collection
over an AOI and date range, derives a chosen radar vegetation index, and renders
its AOI-mean **time series** as an interactive Plotly chart inside the dialog.
Individual dates, multi-date composites, and whole batches can then be exported
to QGIS as styled raster layers.

Processing follows the **Sentinel-1 SAR Backscatter Analysis Ready Data** pipeline
(Mullissa et al., 2021; `ee_s1_ard`), with optional border-noise correction,
terrain flattening, and speckle filtering. Backscatter is delivered in **VV** and
**VH** polarizations (dual-pol `VVVH`), in **dB** or **linear** output, from which
nine dual-pol indices are computed. Radar works through cloud and at night, so the
series is dense and weather-independent, unlike optical sensors.

Code map:

| Layer | File | Responsibility |
|---|---|---|
| View | `view/radar.py` | Three-tab layout (Intro / Inputs / Results), parameter widgets, render/composite/buffer controls, index help text |
| Date filter | `view/sar_date_filter_dialog.py` | Year/month/date checkbox tree for narrowing the active date set |
| Controller | `controllers/sar_ctrl.py` | UI orchestration, worker lifecycle, AOI extraction, buffer, CSV/browser export |
| Service | `services/sar_service.py` | Earth Engine logic: collection build, index bands, time series, composites, GeoTIFF download |
| Worker | `workers/sar_worker.py` | Runs the slow EE/network work off the UI thread (run / preview / composite / batch) |
| Chart render | `view/sar_plot.py` | Builds the self-contained Plotly time-series page (vendored plotly.js v1.58) |
| Renderer | `renderers/sar_renderer.py` | Loads downloaded GeoTIFFs as RGB-composite or single-band pseudocolor QGIS layers |
| GEE auth | `services/gee_service.py` | Earth Engine initialization (high-volume endpoint) |

---

## 0. Architecture & threading

**What it does.** The AOI is read from a QGIS vector layer (or a drawn box) and
converted to an `ee.FeatureCollection` on the **main thread** (QGIS layers are
not thread-safe). The slow Earth Engine + network work then runs inside a
`QThread` subclass, reporting back via `finished` / `failed` (and `progress` /
`cancelled` for batch) signals.

**Methodology.**
- Four dedicated workers cover the four slow operations: `SARWorker` (collection
  build + time series), `SARPreviewWorker` (single-date image), `SARCompositeWorker`
  (multi-date composite), `SARBatchDownloadWorker` (sequential multi-date download).
- The controller holds at most one instance of each, ignores a re-trigger while
  one is running (`isRunning()`), and `deleteLater()`s it on completion via
  `_release_worker`.
- Before any run, `gee_service.is_authenticated` is checked; if false the user is
  sent to the Auth page rather than firing a doomed request.
- Earth Engine is initialized against the **high-volume endpoint**
  (`earthengine-highvolume.googleapis.com`) in `gee_service.py`.

## 1. Data source & ARD pipeline

**What it does.** Builds a Sentinel-1 image collection over the AOI and
`[start_date, end_date]` window through the `ee_s1_ard` `S1ARDImageCollection`
processor, applying the requested radiometric/geometric corrections.

**Methodology.**
- `SARService.get_collection` passes the AOI, dates, polarization, output format,
  and the three correction toggles to `S1ARDImageCollection`, then returns
  `get_collection().sort("system:time_start", False)` — newest first.
- Orbit direction is fixed to **descending** (`ascending=False`).
- Processing options, all defaulted **on** in the Inputs tab:
  - **Border noise correction** — removes low-intensity scene-edge noise.
  - **Terrain flattening** — radiometric terrain normalization (γ⁰).
  - **Speckle filtering** — suppresses the granular SAR speckle.
- **Output format** is `DB` (decibels) or `LINEAR` (linear power); the index help
  text notes some indices (e.g. DPSVIm) assume linear input.
- `ee` and `ee_s1_ard` are imported at service-module load; the dialog itself
  opens without them since the service is only touched on run.

## 2. Polarizations, bands & spectral indices

**What it does.** Each image carries the two polarization bands **VV** and **VH**
plus nine derived dual-pol indices, computed band-by-band over the collection.

**Methodology.**
- Polarization selector offers `VV`, `VH`, `VVVH` (dual-pol, the default) — the
  derived indices need both VV and VH.
- `add_all_index_bands` maps over the collection and appends every index band.
  The index registry (`INDEX_REGISTRY`) maps each UI name → band name, builder
  function, chart title, and y-label. Formulas, as coded:
  - **VV/VH Ratio** (`VVVH_ratio`): `VV / VH`
  - **RVI**: `4·VH / (VV + VH)`
  - **DpRVI**: `VH / (VH + VV)`
  - **CR** (Cross Ratio): `VH / VV`
  - **NDPI**: `(VV − VH) / (VV + VH)`
  - **PD** (Pol Difference): `VV − VH`
  - **DPSVIm**: `VV·(VV + VH) / √2`
  - **PRVI**: `VH·(1 − VH/VV)`
  - **mRVI**: `√(VV/(VV+VH)) · (4·VH/(VV+VH))`
- The **Spectral Index Time Series** picker selects which index drives the chart;
  a live-updating rich-text panel explains the chosen index (formula + use cases).
- Downloaded GeoTIFFs carry all 11 bands in fixed order
  (`VV, VH, VV/VH Ratio, RVI, DpRVI, CR, NDPI, PD, DPSVIm, PRVI, mRVI`); band
  descriptions are written back into the file via GDAL.

## 3. Index time series (in-module chart)

**What it does.** Computes the AOI-mean of the selected index per image date and
plots it as an interactive line chart in the Results tab's web view.

**Methodology.**
- `get_index_timeseries` maps a `reduceRegion(mean, scale=10, maxPixels=1e9)`
  over the collection, formatting each feature as `{date, <band>_mean}`, then
  `getInfo()` pulls it client-side in one round-trip.
- Features with a null mean (no valid pixels that date) are dropped; the rest
  become a pandas DataFrame of `{dates, AOI_average}` held by the controller.
- `sar_plot.render_chart_html` builds a **self-contained** HTML page with the
  vendored **plotly.js v1.58** inlined, so the identical page serves both the
  in-dialog `QWebView` and the "Open in Browser" action. The modern Plotly v6
  template is dropped (`template="none"`) so the JSON stays within what the old
  QtWebKit-compatible engine renders.
- The chart trace is rebuilt by hand (points sorted by date) rather than trusting
  the px figure, for the same old-engine compatibility reason.
- While the run worker is in flight, the web view shows a spinner loading page.

## 4. Date filter (active date set)

**What it does.** A modeless dialog lets the user select a subset of acquisition
dates; the chart, CSV export, and composite all then operate on that subset.

**Methodology.**
- `SARDateFilterDialog` groups the dates into a **year → month → date** checkbox
  tree (built from a pandas datetime grouping), with per-month `(selected/total)`
  counts and Select-All / Deselect-All shortcuts. Year and month checkboxes
  cascade to their children.
- It emits `filter_changed(selected_dates)` live as boxes toggle. The controller
  stores the result as `_active_dates`, or `None` when every date is selected
  (the "no filter" sentinel) so full-set logic stays cheap.
- `_get_active_filtered_dataframe` filters the DataFrame by `_active_dates` for
  the chart and CSV; cancelling the dialog re-emits the pre-open selection.

## 5. Single-date image (preview / download to QGIS)

**What it does.** Fetches one acquisition date as an 11-band GeoTIFF and loads it
into QGIS — either to a temp file (Preview) or to the configured download folder
(Download & Preview).

**Methodology.**
- `get_dataset_image_for_date` filters the collection to `[date, date+1day)`,
  takes `.first()`, selects the 11 bands, and clips to the AOI.
- `download_image` calls `getDownloadURL` (`scale=10`, `EPSG:4326`, GeoTIFF over
  the AOI bounds), `requests.get`s it (300 s timeout, HTTP error raised), writes a
  unique `Sentinel1_<date>.tiff`, and stamps band names via GDAL.
- `SARRenderer.load_sar_to_qgis` honors the chosen **Render Mode**: an
  `RGB: a, b, c` mode maps the three named bands to R/G/B with a per-band 2–98 %
  `cumulativeCut` contrast stretch; a `Band: x` mode builds a single-band
  pseudocolor layer using the selected **Color Ramp** (Viridis, Magma, …). The
  ramp combo is disabled for RGB modes (no effect there). Unknown modes fall back
  to `RGB: VV, VH, VV/VH Ratio`.
- Render-mode item data carries the **canonical English key**, so selection keeps
  working under a translated UI.

## 6. Composite (synthetic image)

**What it does.** Reduces the selected index across the active dates to a single
synthetic image by a chosen statistic, and loads it as a pseudocolor QGIS layer.

**Methodology.**
- `build_band_composite` tags each image with `comp_date`, optionally filters to
  the selected dates (`ee.Filter.inList`), selects the single index band, reduces
  by metric, renames, casts to float, and masks to the AOI geometry.
- Metrics (`aggregate_index_collection`): **Mean, Median, Min, Max, Amplitude**
  (max − min), **Standard Deviation** (`Reducer.stdDev`), **Sum**, and
  **Area Under Curve (AUC)**.
- **AUC** is a trapezoidal time-integral: it stacks the collection to bands and to
  an array, computes day-gaps between consecutive `system:time_start`s relative to
  the start date, sums `Δt·(yᵢ + yᵢ₊₁)/2` along the time axis, and masks to pixels
  valid in every scene (`mask().reduce(min)`).
- `download_band_composite` downloads the single-band GeoTIFF (`scale=10`,
  `EPSG:4326`) to `SAR_<index>_<metric>.tiff`, sanitizing the filename, and
  `load_composite_to_qgis` renders it pseudocolor with the composite color ramp.

## 7. Batch download (all active dates)

**What it does.** Downloads every active date as its own GeoTIFF, with a progress
dialog and cancel, then auto-loads all results into QGIS.

**Methodology.**
- `SARBatchDownloadWorker` loops the active dates **sequentially**, emitting
  `progress(current, total, date)` per item; download failures are swallowed so
  one bad date does not abort the batch.
- Cancellation is cooperative: a `request_cancel` flag guarded by a `QMutex` is
  checked each iteration; partial results are still loaded and reported via the
  `cancelled` signal.
- On completion the controller loads each path with the current render mode and
  ramp, derives the layer label from the filename, and reports `n/total successful`.

## 8. Download buffer

**What it does.** A −300 … +300 m slider grows or shrinks the requested region
applied to every download/preview output (single date, batch, composite).

**Methodology.**
- `_download_aoi` reads the slider; when nonzero it maps
  `feature.buffer(meters).bounds()` over the AOI so the requested region and clip
  share the same margin. At 0 (snapped within ±3 m) it returns the unbuffered AOI.
- A positive buffer includes terrain just outside the AOI; a negative buffer crops
  the edges. The time-series computation always uses the **unbuffered** AOI.

---

## Performance notes

- **Off-thread network** — collection build, time-series fetch, image/composite
  download, and batch all run in `QThread` workers; the dialog stays responsive
  and buttons show a busy label while a worker runs.
- **High-volume endpoint** — Earth Engine is initialized against
  `earthengine-highvolume.googleapis.com`, raising throughput under repeated
  download requests.
- **Single-round-trip time series** — the per-date mean is computed server-side
  with one mapped reducer and a single `getInfo()`, not one request per date.
- **Vendored plotly + cached JS** — plotly.js v1.58 is read from disk once and
  cached in-process; the same self-contained page serves the in-dialog view and
  the browser export, so the chart is byte-for-byte identical in both.
