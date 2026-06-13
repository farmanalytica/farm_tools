# ClimaPlots — Features & Methodology

The ClimaPlots page fetches **decades of daily climate data** for any point on
the map and renders it as **interactive Plotly charts inside the dialog** — no
Earth Engine, no coding. The user picks a coordinate (map click or typed
lon/lat), a data source, and a year range; the module downloads the daily
series, computes annual trends, a thermo-pluviometric diagram, and a set of
ETCCDI climate indices, each shown in its own tab.

Two data sources are interchangeable behind one DataFrame schema: **NASA POWER**
(daily, global, **from 1981**) and **Open-Meteo / ERA5 reanalysis** (daily,
global, **from 1940**). An optional **comparison point B** overlays a second
series on the Trends chart; B may use its own source, so the *same* location can
be compared across NASA POWER and Open-Meteo.

Code map:

| Layer | File | Responsibility |
|---|---|---|
| View | `view/climaplots.py` | Five-tab layout (Intro / Coordinates / Trends / Thermo-pluviometric / Climate Indices), widgets, variable/index descriptions |
| Controller | `controllers/climaplots_ctrl.py` | UI orchestration, pick-point toggles, worker lifecycle, plot rendering, exports |
| Worker | `workers/climaplots_worker.py` | Runs the fetch + index computation off the UI thread |
| Orchestrator | `services/climaplots/orchestrator.py` | Sequences fetch → indices into one `ClimateData` (pure logic, no Qt) |
| Data source | `services/climaplots/nasa_power_service.py` | NASA POWER fetch + derived ET0 / GDD |
| Data source | `services/climaplots/openmeteo_service.py` | Open-Meteo (ERA5) fetch, same schema |
| Indices | `services/climaplots/indices_service.py` | ETCCDI temperature/precipitation indices (climdex) + SPI |
| Stats | `services/climaplots/stats_service.py` | Mann-Kendall trend + Pettitt homogeneity title fragments |
| Plots | `services/climaplots/plot_service.py` | Plotly figure builders (returns `PlotResult`) |
| Export | `services/climaplots/export_service.py` | One-workbook xlsx export (zip-of-CSV fallback) |
| Cache | `services/climaplots/disk_cache.py` | On-disk CSV cache for fetched series |
| Types | `services/climaplots/types.py` | `ClimateData` / `PlotResult` dataclasses (service↔UI contract) |
| Pick tool | `tools/canvas_click_tool.py` | Toggleable map-click coordinate capture (slots A / B) |
| Chart render | `view/plotly_render.py` | Renders figures into QtWebKit `QWebView` / browser |

---

## 0. Architecture & threading

**What it does.** The coordinate is read from the dialog (a map click or typed
lon/lat), then the slow fetch + index computation runs inside a
`ClimaPlotsAnalysisWorker` (`QThread`). Figure building is cheap and reactive, so
it stays on the GUI thread.

**Methodology.**
- The worker emits uniform `finished_ok` / `failed` / `progress` signals; the
  whole `run()` body is wrapped in try/except so any failure surfaces to the UI
  (logged + a warning popup) instead of crashing the thread.
- The worker hands back a single typed `ClimateData` object (raw DataFrame +
  computed indices + echoed coordinates + source keys), keeping the dialog free
  of pandas/xarray details.
- **Lazy heavy imports.** `orchestrator`, `indices_service`, `stats_service`,
  `plot_service` and `export_service` are all imported *inside* methods, not at
  module top, because they pull the extlibs bundle (`climdex`, `pymannkendall`,
  `pyhomogeneity`, `scipy`, `plotly`) that may not be provisioned when the
  plugin first loads.
- Before starting a run the controller checks `_deps_ready()` (tries to import
  `climdex` / `pymannkendall` / `pyhomogeneity`); if missing it warns the user to
  restart QGIS or install `requirements.txt`, rather than throwing.
- A re-entrancy guard skips a new run while a worker is already running. On
  dialog close / page change / cleanup, the worker is disconnected, waited
  briefly, and `deleteLater`-d; temp HTML files are removed.

## 1. Coordinate capture (points A and B)

**What it does.** The user sets point A (required) and an optional comparison
point B by clicking the map canvas or typing lon/lat. Each point keeps its own
colored marker (A red, B blue).

**Methodology.**
- `CanvasClickTool` is a *toggleable* capture mode, not a permanent map-tool
  hijack: `enable(slot)` remembers the user's current map tool and switches to a
  `QgsMapToolEmitPoint`; `disable()` restores it.
- A click is transformed from the canvas CRS to **EPSG:4326** and emitted as
  `point_picked(lon, lat, slot)`, rounded to 4 decimals; the controller fills the
  matching A/B fields. Capture mode stays on until toggled off.
- The A and B pick buttons are **mutually exclusive** (enabling one unchecks the
  other, guarded by `_switching_pick`). If another QGIS tool displaces the
  capture tool, `on_deactivated` syncs the toggle buttons back off.
- Pick A is **auto-enabled** the first time the Coordinates tab is shown. Leaving
  the ClimaPlots page or closing the dialog releases the tool; markers persist
  across runs until "Clear marker".
- Lon/lat fields use `QDoubleValidator` (±180 / ±90). "Same location as A" copies
  A's coordinates into B for a same-point, cross-source comparison.

## 2. Data sources & schema

**What it does.** Fetches the daily climate series for the point and year range
from the selected provider, returning a uniform DataFrame so the rest of the
module is source-agnostic.

**Methodology.**
- **NASA POWER** (`nasa_power_service`) hits the daily point API for
  `T2M_MAX, PRECTOTCORR, T2M_MIN, RH2M, ALLSKY_SFC_SW_DWN, WS2M`, renames them to
  the canonical columns (Max/Min Temperature, Precipitation, Relative Humidity,
  Irradiation, Wind Speed), and replaces the API's `-999.0` fill with `NaN`.
  `MIN_YEAR = 1981`.
- **Open-Meteo / ERA5** (`openmeteo_service`) hits the archive API for the
  equivalent daily variables and maps them to the **same** column names.
  Shortwave radiation is converted MJ/m²/day → kWh/m²/day (`/ 3.6`) to match NASA
  POWER's units; wind is requested in m/s. `MIN_YEAR = 1940`.
- Both expose a matching `fetch(longitude, latitude, proxy, start_year, end_year)`
  and a `MIN_YEAR`; `orchestrator.SOURCES` maps the `"power"` / `"openmeteo"`
  keys to the modules, so adding a source is one dict entry.
- The default end year is the **last complete calendar year** (`today.year − 1`);
  `start_year` is clamped to the source's `MIN_YEAR`. The Coordinates tab
  re-syncs the spinbox floor to the most restrictive source in use (A always; B
  only when it has its own source) via `handle_sync_year_range`.
- **Proxy fallback.** Each request tries the configured proxy first and, on
  failure, retries directly (`timeout=1000`, `verify=True`).

## 3. Derived agronomic variables

**What it does.** Two variables are computed locally rather than fetched:
**Reference ET0** and **Growing Degree Days**.

**Methodology.**
- **Growing Degree Days** = `(Tmean − 10) clipped at 0` per day (base 10 °C),
  where `Tmean = (Tmin + Tmax) / 2`. Computed by both sources.
- **Reference ET0 (Hargreaves)** = `0.0023 · (Tmean + 17.8) · √(Tmax − Tmin) · Ra`,
  with extraterrestrial radiation `Ra` from the FAO-56 formula (inverse
  Earth–Sun distance, solar declination, sunset hour angle) converted MJ/m²/day →
  mm/day (`× 0.408`). NASA POWER derives ET0 this way locally; Open-Meteo returns
  `et0_fao_evapotranspiration` directly from the API.

## 4. Annual trends (Trends tab)

**What it does.** Plots one chosen variable aggregated to an annual series, with
the chart title carrying Mann-Kendall trend and Pettitt homogeneity test results.
A dropdown switches between the eight variables; the comparison point B overlays
a second series.

**Methodology.**
- `_aggregate_annual` sums **Precipitation, Reference ET0, Growing Degree Days**
  per year (annual totals) and means everything else (annual means). Y-axis
  titles encode which aggregation applies.
- The title is built by `stats_service.stats_title`: `pymannkendall.original_test`
  (trend + p-value, α=0.05) and `pyhomogeneity.pettitt_test` (homogeneous vs.
  nonhomogeneous + probable change-point year). Each test is isolated — a failure
  becomes title text, never a crashed plot.
- **Comparison overlay.** When `df_b` is present, A and B are drawn as separate
  `Scatter` traces; statistics are reported for **both** A and B (B's series gets
  its own MK + Pettitt fragment). The legend annotates each series with its data
  source name, so the same point fetched from two sources is distinguishable.
- The builder returns a `PlotResult` (figure + the annual DataFrame for CSV
  export). Switching the variable dropdown re-runs only this cheap builder on the
  GUI thread.

## 5. Thermo-pluviometric diagram (Thermo tab)

**What it does.** Shows the location's mean monthly climate regime: monthly
precipitation as bars plus mean monthly max/min temperatures as lines on a
secondary axis.

**Methodology.**
- Daily data is grouped by (year, month): precipitation summed, temperatures
  averaged; the per-(year,month) frame is then averaged across years to give the
  12-month normals.
- Rendered with a dual-axis `make_subplots` (precipitation bars on the primary
  axis, Max/Min Temperature lines on the secondary). Returns the monthly table as
  the export data.

## 6. Climate indices (Climate Indices tab)

**What it does.** Computes a panel of ETCCDI temperature and precipitation
indices plus a Standardized Precipitation Index, and plots one selected index as
a line, titled with the same MK + Pettitt statistics.

**Methodology.**
- `indices_service.compute` builds an xarray dataset from Precipitation / Max /
  Min Temperature and runs the `climdex` temperature (`tdex`) and precipitation
  (`pdex`) index functions. Indices include annual frost/tropical/icing/summer
  days, monthly TXx/TXn/TNx/TNn, daily temperature range, monthly Rx1day/Rx5day,
  annual R10mm/R20mm, and monthly SDII/CDD/CWD.
- **SPI** is computed in-house: a 90-day rolling precipitation sum, fit to a
  gamma distribution (`scipy.stats.gamma`, `floc=0`), the CDF mapped through the
  inverse normal (`norm.ppf`) to a standardized anomaly.
- **Per-index isolation.** Every index is wrapped in `_try`; a failing index is
  skipped and reported via the `warn` callback (surfaced to the worker's
  `progress` signal / QGIS log) instead of aborting the whole panel. The result
  is a `{index name → DataFrame}` dict; only indices that computed successfully
  appear in the dropdown's data.
- `plot_service.index_plot` picks the plottable column (exact match, sole column,
  or first numeric), titles it with `stats_title`, and raises `PlotDataError`
  (caught → friendly warning) when the selected index has no computed data.

## 7. Rendering (QtWebKit-safe Plotly)

**What it does.** Renders each Plotly figure inside an in-dialog `QWebView`, with
an "Open in browser" full-screen option.

**Methodology.**
- This QGIS build ships only **QtWebKit** (no Chromium/WebEngine), which cannot
  run the site-packages Plotly 6.x bundled plotly.js. `plotly_render` therefore
  uses a **vendored plotly.js 1.58.5** (`assets/`), drops the v6 template
  (`template="none"`), and **decodes Plotly 6.x base64 typed-arrays** (`bdata`)
  into plain lists that the old engine can render.
- The page is written to a temp file and loaded via a `file://` URL (QtWebKit
  renders large embedded charts reliably from a file, unlike `setHtml`). The same
  render feeds both the in-plugin view and "Open in browser", so the chart is
  identical.
- While the worker runs, all three plot views show an animated **loading
  spinner** with the queried coordinates; on failure the spinners are cleared.
  The dialog jumps to the Trends tab immediately so the user sees progress
  instead of a frozen form.

## 8. Exports

**What it does.** The series and charts can be saved as CSV, PNG, or a single
multi-sheet workbook.

**Methodology.**
- **Per-chart CSV** exports the DataFrame stored in the chart's `PlotResult`
  (annual trends, monthly normals, or the selected index); "Save daily data"
  exports the full raw daily series.
- **PNG** is grabbed directly from the rendered web view (`web_view.grab()`).
- **Export all** (`export_service.export`) writes the raw daily table, the
  annual-trends and thermo-pluviometric tables, and every computed index into one
  `.xlsx` (openpyxl), with sheet names sanitized to ≤31 unique chars. If no Excel
  engine is available it falls back to a **`.zip` of CSVs** at the same path.
- Default save location is the OS Downloads folder, falling back to Documents.

---

## Performance notes

- **On-disk cache** — every fetched series is cached as a CSV under the OS temp
  dir (`farm_tools_climaplots_cache`), keyed by source + rounded lon/lat +
  year-range (md5 of the key, `usedforsecurity=False` for Bandit). Historical
  data is immutable, so the cache never needs invalidating; a repeat query for
  the same point/range/source skips the network entirely. All cache operations
  are best-effort and never raise.
- **Source-agnostic schema** — both providers emit the identical column set, so
  caching, indices, plotting and export share one code path regardless of source.
- **GUI-thread figure building** — only the fetch + index computation run in the
  worker; figure builders are cheap and run on the GUI thread, so changing the
  variable/index dropdown re-renders instantly without a new download.
- **Vendored plotly.js** — charts render in QtWebKit via a self-contained local
  plotly.js with typed-arrays pre-decoded, avoiding a CDN round-trip and the
  blank-render failure of the bundled v6 engine.

None of these change the end-user output (same series, same indices, same
charts) — they only make the module faster and keep it working on the QtWebKit
build.
