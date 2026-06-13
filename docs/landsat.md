# Landsat — Features & Methodology

The Landsat page brings **Landsat 7/8/9** imagery into the plugin via Earth
Engine, with **HSV pan-sharpening** as its headline feature — merging the 15 m
panchromatic band into RGB for an effective **15 m "super-resolution"** image.
The user picks an AOI and a date range; Run lists every available acquisition
date over the AOI (tagged by mission) and, in parallel, builds a vegetation-index
time series. From the Results tab any single date can be previewed or downloaded
to QGIS as a super-res RGB (15 m, TOA), a vegetation index (30 m, SR) or a
multispectral RGB composite (30 m, SR); a batch action pulls the super-res image
of every available date.

Coverage is **global** and spans **1999 to present** — Landsat 7 (1999–2022),
Landsat 8 (2013–) and Landsat 9 (2021–). Landsat 5 is **not offered**: it has no
panchromatic band, so pan-sharpening is impossible. The Earth Engine sources are
the Collection 2 archives (`LANDSAT/{sensor}/C02/T1_L2` for Surface Reflectance,
`…/T1_TOA` for Top-of-Atmosphere), wrapped by `agrigee_lite`.

Code map:

| Layer | File | Responsibility |
|---|---|---|
| View | `view/landsat.py` | Three-tab layout (Intro / Inputs / Results), `ls_*` widgets, buffer + coverage sliders |
| Controller | `controllers/landsat_ctrl.py` | UI orchestration, worker lifecycle, date combo, chart + raster rendering |
| Service | `services/landsat_service.py` | All Earth Engine / `agrigee_lite` logic (date discovery, image builders, downloads, batch fan-out) |
| Date worker | `workers/landsat_worker.py` | Lists available `(date, mission)` pairs off the UI thread |
| Preview worker | `workers/landsat_preview_worker.py` | Single-date super-res / index / multispectral download |
| Batch worker | `workers/landsat_batch_worker.py` | Parallel super-res download of every date, with cancel |
| Time-series worker | `workers/landsat_timeseries_worker.py` | Builds the combined L7/8/9 index series (SITS) |
| Satellite wrapper | `extlibs/agrigee_lite/sat/landsat.py` | Band maps, cloud mask, pan-sharpening, SITS compute |
| Chart render | `view/sar_plot.py` | Renders the multi-series index chart (shared with the optical page) |
| GEE auth | `services/gee_service.py` | Earth Engine initialization (high-volume endpoint) |

---

## 0. Architecture & threading

**What it does.** The AOI is read from a QGIS vector layer (or a drawn box) on
the **main thread** (QGIS layers are not thread-safe) and converted to both an
`ee.FeatureCollection` (for image work) and a shapely geometry (for the SITS
time series). Each slow Earth Engine + network operation then runs in its own
`QThread` worker, reporting back via `finished` / `failed` (and `progress` for
the batch) signals.

**Methodology.**
- Four distinct workers, one per task: `LandsatWorker` (date list),
  `LandsatTimeseriesWorker` (index chart), `LandsatPreviewWorker` (single-date
  preview/download) and `LandsatBatchWorker` (all-date super-res). The
  controller owns each worker reference, releases it via `deleteLater()` on
  completion, and guards re-entry with an `isRunning()` check.
- `ee` and `agrigee_lite` are imported **lazily** inside service methods, so the
  dialog opens before the `extlibs` dependency bundle is provisioned (and before
  Earth Engine is authenticated).
- Earth Engine is initialized against the **high-volume endpoint**
  (`earthengine-highvolume.googleapis.com`, in `gee_service.py`), the right fit
  for the parallel batch fan-out below.
- Run requires authentication: if `gee_service.is_authenticated` is false the
  controller shows an "authenticate first" warning and aborts.

## 1. Data source & missions

**What it does.** Every run searches **Landsat 7, 8 and 9 together** over the
AOI/date-range. Each available date is tagged with its mission in the Results
date list (`2021-08-14 — Landsat 8`).

**Methodology.**
- `MISSIONS = ["Landsat 8", "Landsat 9", "Landsat 7"]`; `_mission_class` maps a
  display name to the matching `agrigee_lite` `Landsat7/8/9` class. Landsat 5 and
  10 are not exposed.
- Per-mission date bounds are baked into the wrapper (`startDate`/`endDate`): L7
  `1999-04-15…2022-04-06`, L8 `2013-04-11…`, L9 `2021-11-01…`. A request range
  outside a mission's lifespan simply returns no dates for that mission — no
  error.
- Two product builds back every feature: `_build_sr_sat` (Surface Reflectance,
  `T1_L2`, 30 m, SR scale factors applied) and `_build_superres_sat`
  (Top-of-Atmosphere, `T1_TOA`, pan-sharpened, 15 m). Tier is fixed at 1
  throughout (best geometric accuracy).

## 2. Date discovery (Run)

**What it does.** Lists the acquisition dates available over the AOI for the
chosen range, across all three missions, sorted by date.

**Methodology.**
- For each mission, `list_dated_missions` builds an SR satellite, runs
  `sat.imageCollection(feature)` and pulls the per-image date strings via
  `aggregate_array("ZZ_USER_TIME_DUMMY").getInfo()` — the date tag
  `agrigee_lite` writes during its valid-pixel filtering step.
- Dates are de-duplicated per mission (`set(...)`), paired with the mission name,
  and the merged list is sorted by `(date, mission)`.
- The controller pre-fills the date combo with "Loading dates…", jumps to the
  Results tab immediately, and on completion defaults the selection to the
  **most recent** acquisition (ISO dates sort lexically). An empty result pops a
  warning and bounces back to the Inputs tab.

## 3. Super-resolution RGB (15 m, TOA)

**What it does.** Pan-sharpened real-colour RGB for the selected date, the
page's headline product. Previewed into QGIS (temp file) or downloaded to the
configured folder.

**Methodology.**
- Built on the TOA product with `use_sr=False`, `use_pan_sharpening=True` and
  `bands={blue, green, red, pan}` — `agrigee_lite` raises `ValueError` if
  pan-sharpening is requested on SR or without the `pan` band, so super-res is
  necessarily TOA.
- Pan-sharpening (`ee_l_pan_sharpen`): RGB is reprojected to the 15 m pan
  projection, converted to HSV, the pan band replaces the value channel, then
  converted back to RGB (`hsvToRgb`) — so chroma comes from the 30 m RGB and
  detail from the 15 m pan. The result keeps the red band's mask. `pixelSize` is
  15 m when pan-sharpening, 30 m otherwise.
- The image is `select`-ed into explicit R, G, B band order and clipped to the
  buffered AOI, so the QGIS renderer can always use bands `(1, 2, 3)`.
- Download (`_download`) uses `getDownloadURL` (`format=GeoTIFF`, `EPSG:4326`,
  `scale=pixelSize`, `region=bounds`) + `requests.get` (300 s timeout), writes a
  single multiband GeoTIFF, and stamps band descriptions `red/green/blue` via
  GDAL.

## 4. Vegetation index (30 m, SR)

**What it does.** A single-band vegetation index for the selected date on 30 m
surface reflectance, rendered with a user-chosen colour ramp.

**Methodology.**
- 14 indices are offered (`LANDSAT_INDEX_KEYS`: NDVI, GNDVI, EVI, EVI2, SAVI,
  OSAVI, MSAVI, ARVI, NDWI, MNDWI, BSI, CIgreen, CIred, MCARI). Red-edge indices
  (NDRE, MTCI…) are intentionally absent — Landsat has no red-edge band. Each
  display name maps to an `agrigee_lite` key that must exist in its
  `vegetation_indices`.
- `get_index_image_for_date` builds an SR satellite with `indices={key}`, takes
  the first image of the single-date collection, selects the numeral index band
  (`_numeral_index` resolves the library's `sorted`-order renaming), and clips to
  the buffered AOI.
- The controller renders it as a pseudocolor raster via
  `RasterRendererUtils.load_pseudocolor_raster` with the ramp chosen on the
  Results tab (Viridis / Magma / Plasma / Inferno / RdYlGn / Greys; default
  RdYlGn).

## 5. Multispectral RGB (30 m, SR)

**What it does.** A 3-band false- or true-colour composite from the SR bands for
the selected date.

**Methodology.**
- Four modes (`MULTISPECTRAL_MODES`): Real Color (`red,green,blue`),
  NIR-Red-Green, SWIR1-NIR-Red, SWIR2-NIR-Green. The combo stores the stable
  English key as `itemData` so the renderer survives a translated UI.
- `get_multispectral_image_for_date` resolves each friendly band name to its
  numeral name (`_numeral_band`), selects the three into `r, g, b` display order,
  and clips to the buffered AOI.
- Downloaded as a single 3-band GeoTIFF and loaded with the same
  cumulative-cut RGB renderer as super-res (`_add_rgb_raster`, bands `(1,2,3)`).

## 6. Index time series (SITS)

**What it does.** Plots the chosen index across all three missions over the
date range, one trace per mission, in the Results web view. Built **automatically
by Run**, in parallel with the date list.

**Methodology.**
- Per mission, `get_index_timeseries` calls `agrigee_lite`'s
  `download_single_sits` (server-side `computeFeatures`, no raster download) with
  the chosen spatial reducer (median or mean) and returns a DataFrame.
- The request is **clipped to `mission_lifespan ∩ requested_range`** before the
  call, so a range that only partly (or doesn't) overlap a mission is handled
  cleanly — non-intersecting missions return an empty frame, partial ones query
  only their valid sub-window. A `ValueError` (no intersection) is swallowed to
  an empty frame.
- `get_index_timeseries_df` concatenates the three frames into one
  (`dates, AOI_average, mission`), sorted by date; one mission failing (quota,
  range) is caught and skipped so the others still plot.
- The chart is rendered by `render_multiseries_chart_html` (shared with the
  optical/SAR pages), grouped by `mission` with fixed per-mission colours, into a
  temp HTML file loaded in `ls_web_view`. "Open in Browser" re-renders the same
  figure with the toolbar enabled.

## 7. Batch super-res download (all dates)

**What it does.** Downloads the pan-sharpened super-res RGB of **every** available
`(date, mission)` pair to the configured folder, with a modal progress dialog
and cancel, then loads each result into QGIS.

**Methodology.**
- `download_superres_batch` runs the per-scene pipeline **concurrently** with
  pure asyncio: each scene's blocking `getDownloadURL` resolve + `requests.get` +
  write is offloaded with `asyncio.to_thread`, a `Semaphore` caps the in-flight
  count at **40**, and each scene has a 420 s `wait_for` timeout. A failing scene
  returns `None` and is skipped, not fatal.
- Each scene is requested as a single multiband GeoTIFF in R, G, B order
  (identical output to the single-date super-res path), so there is no zip
  extraction or band merging. This drops the prior dependency on `agrigee_lite`'s
  aria2 downloader (and its native `aria2c` binary), which upstream removed.
- `progress_cb(done, total)` updates the `QProgressDialog`; `cancel_cb` is polled
  per scene so the dialog's Cancel stops queuing and waiting. Cancelled vs.
  finished are distinct signals — both still load whatever downloaded.

## 8. Cloud masking & min-valid coverage filter

**What it does.** An optional QA_PIXEL cloud mask and a "minimum valid coverage"
slider gate which dates survive and what every preview/download contains.

**Methodology.**
- **Cloud mask (on by default).** On SR the `ee_l_mask` QA_PIXEL bitmask removes
  clouds, cloud shadows, cirrus, dilated clouds and saturated pixels; on TOA an
  additional Landsat Simple Cloud Score filter is applied
  (`toa_cloud_filter_strength`, default 15). Disabling it yields more dates but
  far noisier imagery.
- **Min valid coverage (slider, default 80%).** `_apply_min_valid` converts the
  percentage into `agrigee_lite`'s absolute `minValidPixelCount` =
  `pct/100 × AOI_area_m² / pixelSize²`. Because super-res (15 m) and SR (30 m)
  have different `pixelSize`, the same percentage maps to a different pixel count
  on each — hence it is computed per satellite, not as a constant. 0% leaves the
  library default. The threshold applies uniformly to the date list, the time
  series and every preview/download, so all three agree on which dates are
  "valid".
- The AOI's ellipsoidal area (`aoi_area_m2`, measured on the main thread) feeds
  this conversion and is passed through every worker.

## 9. Download buffer

**What it does.** A −300 m … +300 m slider that grows or crops the requested
region around the AOI for every preview and download.

**Methodology.**
- A positive value buffers the AOI geometry outward (`geometry.buffer(m)`);
  negative crops inward; the `[-3, +3]` m centre is a dead-zone snapped to 0.
- `_region` applies the buffer before `getDownloadURL`'s `region=bounds`, so the
  buffer affects super-res, index and multispectral exports identically.

---

## Performance notes

- **Parallel batch download** — all dates fetch concurrently (asyncio +
  semaphore, cap 40) instead of serially; the dominant cost was sequential
  network round-trips. Output is byte-identical to the serial per-scene path.
- **High-volume endpoint** — Earth Engine is initialized against
  `earthengine-highvolume.googleapis.com`, raising throughput and easing rate
  limits under the parallel fan-out.
- **Concurrent Run** — Run starts the date-list worker and the time-series worker
  together, so the chart and the date list are produced in parallel rather than
  one after the other.
- **Single multiband GeoTIFF** — each scene is one GeoTIFF in display band order,
  avoiding zip extraction / band merging and the removed `aria2c` native binary.

None of these change the end-user output (same GeoTIFFs, same stats, same chart)
— they only make the module faster and more responsive.
