# SYSI — Features & Methodology

The SYSI (**Synthetic Soil Image**) page builds a **bare-soil reflectance
composite** from a multi-temporal Sentinel-2 collection and loads it into QGIS
as a styled raster layer. It runs the **GEOS3** (Geospatial Soil Sensing System)
bare-soil detection of Demattê et al. (2018) entirely on Google Earth Engine:
scenes are filtered, every pixel is tested against a set of spectral conditions,
only pixels that are bare soil are kept, and the surviving pixels are reduced
with a temporal **median**. The output reveals the underlying soil surface free
of vegetation and crop residue.

The input is Sentinel-2 surface reflectance
(`COPERNICUS/S2_SR_HARMONIZED`, **10 m**); processing is server-side and the
result is downloaded as a single 9-band float32 GeoTIFF
(Blue, Green, Red, Rededge2, NIR, SWIR1, SWIR2, NDVI, NBR2). There is no
in-module raster preview — the only visualization is the QGIS layer itself.

Code map:

| Layer | File | Responsibility |
|---|---|---|
| View | `view/sysi.py` | Two-tab layout (Intro / Inputs), widgets, AOI / date / month / threshold / cloud / buffer controls |
| Controller | `controllers/sysi_ctrl.py` | UI orchestration, param collection, AOI extraction + buffer, worker lifecycle, QGIS layer styling |
| Service | `services/sysi_service.py` | All Earth Engine logic (GEOS3 pipeline, median composite, GeoTIFF download, band naming) |
| Worker | `workers/sysi_worker.py` | Runs the slow EE/network composite + download off the UI thread |
| GEE auth | `services/gee_service.py` | Earth Engine initialization (high-volume endpoint) |

---

## 0. Architecture & threading

**What it does.** The AOI is read from a QGIS vector layer (or a drawn box) and
converted to an `ee.FeatureCollection` on the **main thread** (QGIS layers are
not thread-safe). The slow Earth Engine + network work then runs inside a
`SYSIWorker` (`QThread`), which reports back via `finished` / `failed` signals.

**Methodology.**
- `AOIService.get_ee_feature_colection_from_layer` builds the
  `ee.FeatureCollection` on the main thread before the worker is started; the
  feature collection (already buffered, see §1) is passed into the worker.
- The worker's `finished(output_path, label)` signal carries the local GeoTIFF
  path; `failed(error_message)` carries any exception text raised during build
  or download. The controller branches on these to load the layer or pop a
  warning.
- The Generate button is disabled (and relabelled "Generating…") while the
  worker runs, and a re-entrancy guard in `handle_generate_sysi` rejects a
  second submission while `_worker.isRunning()`.
- Earth Engine is initialized against the **high-volume endpoint**
  (`earthengine-highvolume.googleapis.com`) by `gee_service.py`.

## 1. Inputs & AOI

**What it does.** The Inputs tab collects the AOI layer, a start/end date, a
month filter, NDVI and NBR2 threshold ranges, a per-tile cloud-cover threshold,
and a download buffer. `_read_params` packs these into the dict the worker
consumes.

**Methodology.**
- **AOI.** Selected from a vector-layer combo or drawn on the canvas
  (`start_draw_aoi`). Generation requires a selected layer and GEE
  authentication; both are validated before the worker starts.
- **Dates.** `start_date` / `end_date` are `yyyy-MM-dd` strings; the default
  range is `2017-03-28` (start of the S2 SR archive) to today. The controller
  rejects `start >= end`.
- **Months.** Twelve checkboxes (`sysi_month_checks`, all checked by default)
  map to month numbers 1–12; at least one must be selected.
- **Download buffer.** A −300…+300 m slider expands or crops the AOI before
  download. `_download_aoi` snaps values within ±3 m to 0 (dead zone), and when
  non-zero applies `feature.buffer(meters).bounds()` per feature — so the buffer
  reshapes the *download bounding box*, not just the clip.

## 2. Scene collection & cloud filtering

**What it does.** Builds the Sentinel-2 collection, masks clouds with the QA60
band, and filters by AOI, cloud-cover percentage, and the selected months.

**Methodology.**
- Source collection: `COPERNICUS/S2_SR_HARMONIZED`, filtered by
  `filterDate(start, end)`, `filterBounds(aoi)`, and
  `CLOUDY_PIXEL_PERCENTAGE < cloud_threshold` (scene-level / per-tile cut).
- **QA60 cloud mask** (`_mask_s2_clouds`): bit 10 (opaque clouds) and bit 11
  (cirrus) must both be 0; matching pixels are kept via `updateMask`.
- Bands `B2, B3, B4, B6, B8, B11, B12, QA60` are renamed to
  `Blue, Green, Red, Rededge2, NIR, SWIR1, SWIR2, QA60`.
- **Month filter.** Each scene is tagged with its calendar month from
  `system:time_start`, then the collection is filtered with
  `ee.Filter.inList('month', selected_months)`.
- **Empty-collection guards.** The collection size is materialized with
  `getInfo()` after the date/cloud filter and again after the month filter; an
  empty result at either stage raises a `RuntimeError` with an actionable
  message (extend dates / raise cloud threshold / enable more months) instead of
  producing an empty composite.

## 3. Spectral indices

**What it does.** Per scene, computes the indices GEOS3 needs: NDVI, NBR2, and
the two visible-slope differences GRBL and REGR.

**Methodology** (`_add_indexes`).
- `NDVI = normalizedDifference(NIR, Red)`.
- `NBR2 = normalizedDifference(SWIR1, SWIR2)`.
- `GRBL = Green − Blue` (rising green-over-blue visible slope).
- `REGR = Red − Green` (continues the rising slope).
- GRBL and REGR are computed **before** the surface-reflectance scale factor is
  applied; the GEOS3 condition only tests their sign (`> 0`), which is
  scale-invariant, so the ordering is intentional.

## 4. Scale factors

**What it does.** Converts the raw integer DN bands to surface reflectance in
[0–1].

**Methodology** (`_apply_scale_factors`).
- The optical bands (and QA60, kept only for mask bookkeeping) are divided by
  `10000` and written back over the originals via
  `addBands(optical, None, True)`.

## 5. GEOS3 bare-soil mask

**What it does.** Tests every pixel against the GEOS3 rule and keeps only those
that are bare soil; also drops black-border no-data pixels.

**Methodology — GEOS3 rule** (`_make_geos3_mapper`). A pixel is bare soil when
**all** hold:
- `NDVI` within `[ndvi_min, ndvi_max]` — low vegetation.
- `NBR2` within `[nbr_min, nbr_max]` — limits crop residue / non-photosynthetic
  vegetation.
- `VNSIR ≤ 0.9` — visible-to-SWIR tendency. `VNSIR = 1 − (2·Red − Green − Blue
  + 3·(NIR − Red))`; the **0.9** threshold is fixed in code (`_VNSIR_THRESHOLD`)
  and not exposed in the UI.
- `GRBL > 0` (Green > Blue) and `REGR > 0` (Red > Green) — the rising visible
  slope characteristic of soil.

The combined boolean is added as a `GEOS3` band.

**Methodology — masking** (`_mask_by_geos3`).
- Keeps pixels where `GEOS3 == 1` **and** `SWIR2, Green, Red, Blue` are all
  `≥ 0`, the latter four dropping the negative-valued black-border no-data
  pixels left after cloud masking.

## 6. Median composite & export image

**What it does.** Reduces the masked per-scene soil pixels into one composite
and shapes it for download.

**Methodology.**
- The bare-soil collection is reduced with `.median()` — for each pixel the
  median over all dates where it was classed as bare soil. This removes
  transient moisture and fills cloud/vegetation gaps with values from other
  dates.
- The composite selects the 9 export bands
  (`Blue, Green, Red, Rededge2, NIR, SWIR1, SWIR2, NDVI, NBR2`), casts to
  `toFloat()`, and clips to the AOI geometry.

## 7. Download & QGIS load

**What it does.** Downloads the composite as a GeoTIFF, writes band names into
its metadata, and loads it into QGIS as a natural-colour RGB layer.

**Methodology.**
- **Download** (`download_composite`): `getDownloadURL` with `scale=10`,
  `format=GeoTIFF`, `crs=EPSG:4326`, and `region` = the AOI's
  `bounds().getInfo()`. The response is fetched with `requests.get`
  (300 s timeout); a non-OK HTTP status raises a `RuntimeError`. The file is
  written to the configured download folder (falling back to the system temp
  dir), with `_get_unique_path` appending `_1, _2, …` to avoid clobbering.
- **Band names** (`_set_band_names`): if GDAL is available, each raster band's
  description is set to its export-band name; failures are swallowed so a
  missing/locked GDAL never blocks the download.
- **QGIS styling** (`_load_sysi_to_qgis`): the layer is loaded with CRS
  `EPSG:4326` and a `QgsMultiBandColorRenderer` set to **natural colour**
  (R = band 3, G = band 2, B = band 1). Each of the three display bands gets a
  **2–98 % cumulative-cut** stretch (`StretchToMinimumMaximum`) computed over
  the current canvas extent (falling back to the layer extent); the stretch
  block is wrapped in a try/except so a failed cut leaves a usable layer. The
  layer is added and inserted at the top of the layer tree.

---

## Performance notes

- **Off-thread pipeline** — the entire GEOS3 build + GeoTIFF download runs in a
  `QThread`, keeping the dialog responsive while EE resolves the composite.
- **High-volume endpoint** — Earth Engine is initialized against
  `earthengine-highvolume.googleapis.com`, raising throughput under load.
- **Early empty-collection guards** — collection size is checked after the
  date/cloud filter and again after the month filter, so an over-restrictive
  filter fails fast with a clear message instead of producing an empty raster or
  a slow downstream error.
