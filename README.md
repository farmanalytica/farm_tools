# FARM tools — QGIS plugin for vegetation-index time series & imagery

FARM tools is a QGIS plugin by [FARM Analytica](https://www.farmanalytica.com.br) that
integrates **Google Earth Engine (GEE)** into QGIS for vegetation-index time
series, multispectral/SAR imagery download, terrain, soil and climate products. It
targets students, researchers, farmers, and professionals in agriculture, land
monitoring, and environmental management.

FARM tools is a fork of the RAVI plugin with a distinct plugin identity (folder
`farm_tools`, name "FARM tools", own menu/toolbar), so it can be installed and run
**side-by-side with RAVI** in the same QGIS profile.

- **Homepage:** https://www.farmanalytica.com.br
- **Repository:** https://github.com/farmanalytica/farm_tools
- **Issues:** https://github.com/farmanalytica/farm_tools/issues
- **License:** GPL v2 or later (see [`LICENSE`](LICENSE))

## Features

| Domain | What it does |
|---|---|
| **Optical** (Sentinel-2) | Vegetation-index time series, per-point / per-feature analysis, cloud (SCL) filtering, image preview, composites, multispectral download |
| **SAR** (Sentinel-1) | Backscatter retrieval, date filtering, plotting, styled rendering |
| **Multi-Satellite** | Multi-mission index time series and imagery — Landsat 7/8/9, Sentinel-2, HLS, MODIS — with 15 m HSV pan-sharpening on the pan-capable Landsat sensors, via `agrigee-lite` |
| **EasyDEM** | Digital Elevation Model catalog browse + AOI-aware download + Magma elevation rendering |
| **SYSI** | Synthetic Soil Image (bare-soil reflectance composite) generation |
| **ClimaPlots** | Climate trends, indices and thermo diagrams from NASA POWER / Open-Meteo daily data |
| **Field Guide** | Per-feature / per-point raster sampling with adjustable buffer + PDF report export |
| **MapBiomas** | In-module MapBiomas Brasil Collection 10 land-use/land-cover viewer: annual coverage (1985–2024) browsed by a year slider, plus configurable source→target first-transition analysis (presets + custom classes) with a converted-area bar chart and map that filter live to a year-range slider. Export any coverage year, or the range-limited transition, to QGIS as a styled raster. See [docs/mapbiomas.md](docs/mapbiomas.md) |
| **GEE Configuration** | GEE sign-in — personal OAuth **and** service-account key |

## Requirements

- **QGIS 3.28+ and QGIS 4.x** (Python 3.11 / 3.12 / 3.13; QGIS 3.44 LTR ships 3.12)
- A **Google Earth Engine** account + a Cloud project with the Earth Engine API enabled
- Third-party Python deps (`earthengine-api`, `agrigee-lite`, `google-*`, …) are
  **provisioned automatically** on first launch — see
  [Dependency provisioning](#dependency-provisioning).

## Installation

Install from the QGIS Plugin Manager, or clone into the QGIS plugin directory:

```
<QGIS profile>/python/plugins/farm_tools
```

On first activation FARM tools downloads its dependency bundle (or pip-installs
as a fallback), then prompts for Earth Engine sign-in.

---

## Architecture

FARM tools follows a layered **MVC-style** design. The Qt UI never talks to the Earth
Engine SDK directly; all remote work flows through a service layer and runs on
background threads so the QGIS UI stays responsive.

```
                 QGIS  ──classFactory──▶  __init__.py
                                            │  (boots extlibs, then loads FarmTools)
                                            ▼
                                       farm_tools.py  (FarmTools plugin class)
                                            │  builds menu/toolbar action
                                            ▼
                                  farm_tools_dialog.py  (main dialog + sidebar)
                                            │
            ┌───────────────────────────────┼───────────────────────────────┐
            ▼                                ▼                                ▼
       view/  (Qt widgets)   ◀──▶   controllers/  (per-feature glue)   ──▶  managers/ (settings, datasets)
                                            │
                       ┌────────────────────┼────────────────────┐
                       ▼                                          ▼
                  services/  (GEE + data business logic)     tools/  (map tools: AOI draw, point capture)
                       │
                       ▼
                  workers/  (QThread — run services off the UI thread)
                       │  results emitted via Qt signals
                       ▼
                  renderers/  (style results into QgsRasterLayer / map layers)
```

### Layers

| Layer | Path | Responsibility |
|---|---|---|
| **Entry / bootstrap** | `__init__.py`, `farm_tools.py` | `classFactory` provisions deps then instantiates `FarmTools`; the plugin class wires the QGIS menu/toolbar and opens the dialog. |
| **Dialog / shell** | `farm_tools_dialog.py`, `view/sidebar.py`, `view/welcome.py`, `view/styles.py` | Main window, navigation sidebar, welcome hub (module-grid landing page), shared styling. |
| **View** | `view/` | Per-feature panels (`optical`, `radar`, `landsat`, `sysi`, `download_dem`, `climaplots`, `fieldguide`, `mapbiomas`, `auth`, …), the `welcome` hub, dialogs, plots (`sar_plot`, `plotly_render`), custom widgets (`range_slider`). Pure Qt — no business logic. |
| **Controllers** | `controllers/` | One per feature (`auth`, `optical`, `sar`, `dem`, `landsat`, `sysi`, `climaplots`, `fieldguide`, `mapbiomas`). Translate UI events into service/worker calls and push results back to layers and views. |
| **Services** | `services/` | Business logic. `gee_service.py` owns all Earth Engine auth/init; feature services (`optical`, `sar`, `dem`, `landsat`, `sysi`, `fieldguide`, `mapbiomas`, `aoi`, `nasa_power`) and the `climaplots/` package build EE/HTTP queries and return plain data (DataFrames / dicts). |
| **Workers** | `workers/` | `QThread` subclasses that run a service call off the UI thread and emit `finished` / `failed` signals (e.g. `optical_worker`, `landsat_batch_worker`, `climate_worker`, `mapbiomas_worker`). |
| **Renderers** | `renderers/` | Turn results into styled QGIS layers (`base_maps`, `dem_renderer`, `sar_renderer`, `raster_renderer_utils`). |
| **Managers** | `managers/` | Cross-cutting state — `settings_manager` (QgsSettings), `dataset_manager` (catalogs). |
| **Tools** | `tools/` | QGIS map tools (`aoi_draw_tool`, `point_capture_tool`) and the vegetation-index definitions (`indexes.py`). |
| **Assets / UI / i18n** | `assets/`, `ui/`, `i18n/` | Icons & logos, HTML onboarding pages, Qt translations. |

### Codebase layout

```
farm_tools/
├── __init__.py              # classFactory — provisions extlibs, returns FarmTools
├── farm_tools.py            # FarmTools plugin class — translator, menu/toolbar, controller wiring
├── farm_tools_dialog.py     # FarmToolsDialog — QStackedWidget shell (loading + welcome hub + feature pages)
├── extlibs_manager.py       # dependency provisioning + ExtlibsDownloader(QThread)
├── requirements.txt         # pinned third-party deps (earthengine-api, agrigee-lite==3.0.0, …)
├── build_plugin.py          # package → dist/farm_tools.zip
├── build_extlibs_zip.py     # build a tagged extlibs-<cpXY>-<platform>.zip
├── compile_translations.py  # i18n/*.ts → *.qm
├── icon.png                 # plugin-manager / dialog-header icon (rendered from assets/logo.svg)
├── toolbar_icon.png         # toolbar action icon (rendered from assets/farm.svg)
├── controllers/             # auth, dem, optical, sar, landsat, sysi, climaplots, fieldguide, mapbiomas  (UI ↔ worker ↔ service glue)
├── services/                # gee_service + per-feature EE/data logic (stateless) + climaplots/ package
├── workers/                 # QThread subclasses — run a service off the UI thread
├── view/                    # welcome hub + setup_<feature>_page builders, sidebar, dialogs, plots, widgets
├── renderers/               # results → styled QgsRasterLayer
├── managers/                # settings_manager, dataset_manager
├── tools/                   # aoi_draw_tool, point_capture_tool, indexes.py
├── assets/  ui/  i18n/       # icons/catalogs, HTML intro pages, translations
└── extlibs/                 # provisioned at runtime — NOT committed (except tagged *.zip bundles)
```

### One feature = one slice through every layer

Each data module (`auth`, `optical`, `sar`, `dem`, `landsat`, `sysi`, `climaplots`, `fieldguide`, `mapbiomas`)
appears once per layer. To work on a feature, follow its name across the tree:

| Feature | view | controller | service | worker(s) |
|---|---|---|---|---|
| **Auth** | `view/auth.py` | `AuthCtrl` | `GEEService` | `AuthWorker`, `AuthStatusWorker` |
| **Optical** (S2) | `view/optical.py` | `OpticalCtrl` | `OpticalService` | `OpticalWorker`, `OpticalPreviewWorker`, `OpticalCompositeWorker`, `OpticalAnalysisWorker`, `BatchDownloadWorker`, `ClimateWorker` |
| **SAR** (S1) | `view/radar.py` | `SARCtrl` | `SARService` | `SARWorker`, `SARPreviewWorker`, `SARCompositeWorker`, `SARBatchDownloadWorker` |
| **Landsat** | `view/landsat.py` | `LandsatCtrl` | `LandsatService` | `LandsatWorker`, `LandsatPreviewWorker`, `LandsatTimeseriesWorker`, `LandsatBatchWorker` |
| **DEM** (EasyDEM) | `view/download_dem.py` | `DEMCtrl` | `DEMService`, `DEMRegistry` | `DatasetAvailabilityWorker`, `DemDownloadWorker` |
| **SYSI** | `view/sysi.py` | `SYSICtrl` | `SYSIService` | `SYSIWorker` |
| **ClimaPlots** | `view/climaplots.py` | `ClimaPlotsCtrl` | `services/climaplots/` package | `ClimaPlotsAnalysisWorker` |
| **Field Guide** | `view/fieldguide.py` | `FieldGuideCtrl` | `FieldGuideService`, `fieldguide_pdf/` | — (synchronous, local raster sampling) |
| **MapBiomas** | `view/mapbiomas.py` | `MapBiomasCtrl` | `MapBiomasService` | `MapBiomasWorker` |

Shared services not tied to one feature: `aoi_service.py` (QGIS layer → WGS84 EE FeatureCollection),
`nasa_power_service.py` (climate series for the optical climate overlay) and `raster_analysis.py`
(local raster value extraction, used by Field Guide).

### Conventions

- **View pages are functions, not classes.** Each `view/<feature>.py` exposes a
  `setup_<feature>_page(dialog, page)` builder that populates a `QWidget` and hangs the
  child widgets off the `dialog` (e.g. `dialog.s2_btn_run`). Controllers read/write those
  attributes — there's no separate view object.
- **Navigation** is signal-driven: `view/sidebar.py::Sidebar` emits `welcome_requested`,
  `auth_requested`, `optical_requested`, `sysi_requested`, `radar_requested`, `dem_requested`,
  `landsat_requested`, `fieldguide_requested`, `climaplots_requested`, `mapbiomas_requested`; `FarmToolsDialog`
  switches the `QStackedWidget` page in response. The welcome hub (`view/welcome.py`) is also a
  landing page of clickable module cards that navigate via the dialog's `show_*_page` methods.
- **Controllers** take `(dialog, …)` with `gee_service` and `interface` (the QGIS `iface`)
  passed in; they own no Qt widgets of their own. All wiring (button `clicked` → handler) is
  done once in `farm_tools.py::_finish_init()`.
- **Workers** are `QThread` subclasses with a uniform contract: a `finished(...)` signal
  carrying the result and a `failed(str)` signal carrying the error message. `run()` wraps the
  service call in try/except and emits one or the other. (Exceptions: `AuthWorker` uses
  `browser_opened(str)` + `finished_auth(bool, str)`; `ClimaPlotsAnalysisWorker` uses
  `finished_ok` / `failed` / `progress`.) Never call Earth Engine from a controller
  directly — always go through a worker so the UI thread never blocks.
- **Services are stateless and return plain data** (DataFrames / lists of dicts / file paths).
  Only `GEEService` holds state (the authenticated EE session). Services must not import `ee`
  at module top level — import lazily inside methods so dialogs load before extlibs are
  provisioned.

### Settings (QgsSettings keys)

Config persists in QGIS settings under two prefixes. **These keys are intentionally
shared with RAVI**, so an existing RAVI sign-in (GEE project ID, auth mode,
service-account key path) and download/proxy preferences carry over to FARM tools:

| Key | Owner | Purpose |
|---|---|---|
| `MyPlugin/projectID` | `GEEService` | Google Cloud project ID |
| `MyPlugin/authMode` | `GEEService` | `personal` (OAuth) or `service` (SA key) |
| `MyPlugin/serviceAccountKeyPath` | `GEEService` | Path to service-account JSON |
| `qgis-RAVI/dem_download_folder` | `SettingsManager` | Default download folder |
| `qgis-RAVI/proxy` | `SettingsManager` | Optional HTTP(S) proxy URL |

Saved values are restored in `farm_tools.py::_finish_init()` on startup.

### Internationalization

UI strings are wrapped for Qt translation and shipped as compiled `.qm` files in `i18n/` for
six locales: `es`, `fr`, `hi`, `it`, `pt_BR`, `zh_CN`. At startup `farm_tools.py` reads the QGIS
locale, maps short codes (`pt`→`pt_BR`, `zh`→`zh_CN`), loads `i18n/farm_tools_<locale>.qm` via a
`QTranslator`, and installs it globally. The Qt translation **context** is `"RAVI"` (kept from
the upstream `.ts`/`.qm` files so the compiled translations keep matching). Edit the `.ts`
source, then run `python compile_translations.py` to regenerate the `.qm` bundles.

### Request flow (example: optical time series)

1. User sets an AOI and parameters in `view/optical.py`.
2. `controllers/optical_ctrl.py` collects params + AOI geometry and starts an
   `OpticalWorker` (`workers/optical_worker.py`).
3. The worker calls `OpticalService.get_time_series(...)` (`services/optical_service.py`),
   which builds the Earth Engine query through the authenticated `GEEService`.
4. On completion the worker emits `finished(data, index_name)`; the controller
   renders the chart / writes the layer via the renderers.

This keeps Earth Engine I/O on a background thread — the QGIS UI never blocks.

### Onboarding: adding a new feature

A new data module touches each layer in the same order the request flows. Mirror an
existing feature (`optical` is the most complete reference):

1. **Service** (`services/<feature>_service.py`) — a stateless class that builds the EE
   query and returns plain data. Import `ee` lazily inside methods.
2. **Worker** (`workers/<feature>_worker.py`) — `QThread` subclass; `run()` calls the
   service and emits `finished(result)` / `failed(str)`.
3. **View** (`view/<feature>.py`) — a `setup_<feature>_page(dialog, page)` builder that
   adds widgets to `dialog`.
4. **Controller** (`controllers/<feature>_ctrl.py`) — reads widget values, starts the
   worker, renders results on `finished`.
5. **Sidebar + dialog** — add a nav button + `<feature>_requested` signal in
   `view/sidebar.py`, a page in `farm_tools_dialog.py`, and instantiate the controller + wire its
   buttons in `farm_tools.py::_finish_init()`.
6. **Renderer** (`renderers/`) if the result is a layer; **i18n** — wrap new strings and
   recompile.

### Dependency provisioning

FARM tools needs packages **not shipped with QGIS** (`earthengine-api`, `agrigee-lite`,
`google-*`, `cryptography`, `cffi`, …). These are ABI-locked to the Python
version, so a single bundle breaks across QGIS releases. `extlibs_manager.py`
resolves this at runtime, in order:

1. **Download a tagged prebuilt bundle** — `extlibs-<cpXY>-<platform>.zip`
   matching the running interpreter (`cp312-win_amd64`, …) from the repository.
2. **Fallback to pip** — install `requirements.txt` into `extlibs/` using the
   QGIS Python.
3. Otherwise show manual instructions.

A `extlibs/.ready` sentinel records the active tag, so a QGIS Python upgrade
(different tag) re-provisions automatically. QGIS-provided packages
(`numpy`, `pandas`, `scipy`, `requests`, …) are deliberately **never** shadowed
from `extlibs/`.

### Build & CI

| Script / workflow | Purpose |
|---|---|
| `build_extlibs_zip.py` | Build a tagged `extlibs-*.zip` for the host (or cross-target a platform via `_PYTHON_HOST_PLATFORM`, e.g. macOS `universal2`). |
| `.github/workflows/build-extlibs.yml` | Build the full matrix (Windows / Linux / macOS × Python 3.11–3.13) and optionally commit the bundles to `main`. |
| `build_plugin.py` | Package the plugin for distribution (`dist/farm_tools.zip`). |
| `compile_translations.py` | Compile `i18n/` `.ts` → `.qm`. |

> Dependency versions are pinned in `requirements.txt` (e.g. `agrigee-lite==3.0.0`),
> so bundle bytes are reproducible — a rebuild only changes a zip when its resolved
> dependency set changes.

---

## Contributing

Issues and pull requests welcome at the
[project repository](https://github.com/farmanalytica/farm_tools).

## License

GNU General Public License v2.0 or later. See [`LICENSE`](LICENSE).
