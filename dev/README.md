# Dev notebooks — feature exploration

Functional Jupyter notebooks that prototype the RAVI features whose front-end
exists in `view/` but whose backend (Earth Engine / service logic) is **not yet
wired**. Each notebook is grounded in the original implementation on the
`legacy` branch and is meant to be run top-to-bottom to validate the approach
before porting it into a controller/service.

## Running

Each notebook is self-contained:

1. Authenticate via a service-account key — set the `GEE` env var to the key
   path; the setup cell calls `ee.ServiceAccountCredentials(None, os.environ["GEE"])`
   then `ee.Initialize(credentials)` (same as `testing.ipynb`).
2. Run all cells. The AOI is loaded from `contorno_area_total.zip` via
   `load_aoi_from_shapefile(...)` (same area as `testing.ipynb`); each notebook's
   date range is defined up front — edit it freely.

Dependencies vary per notebook: `earthengine-api` (all but #09), `pandas`,
`plotly`/`matplotlib`, `scipy` (#04), `requests` (#05/#06/#09). `geemap` is
optional and guarded where used.

## Notebooks → features (issues.md)

| Notebook | Feature | Issues |
|----------|---------|--------|
| `01_s2_collection_and_cloud_masking.ipynb` | S2 Harmonized SR loading, scene cloud %, SCL class masking, AOI-local valid pixels, AOI coverage, unique-day | #7, #8 |
| `02_vegetation_indices.ipynb` | All 19 built-in vegetation indices (formulas + band aliasing) | #1, #3 |
| `03_custom_vegetation_index.ipynb` | Custom band-expression index builder | #2 |
| `04_timeseries_and_filtering.ipynb` | AOI-average VI time series, Savitzky-Golay smoothing, **client-side re-filtering of cached metadata (no new GEE call)** | #1, #11 |
| `05_multispectral_rgb.ipynb` | True-color / false-color RGB + custom RGB composite | #4, #5 |
| `06_single_and_batch_download.ipynb` | Single-date & batch GeoTIFF download, per-date selection, AOI buffer | #6, #10 |
| `07_synthetic_composite.ipynb` | Temporal composite metrics (mean/median/min/max/amplitude/std/sum/AUC) | — |
| `08_sysi_soil_image.ipynb` | SYSI bare-soil composite (GEOS3 masking) | #12, #13 |
| `09_nasa_power_climate.ipynb` | NASA POWER daily climate fetch + plot overlay + CSV | #14 |
| `10_point_and_feature_analysis.ipynb` | Per-point & per-feature VI series, valid-pixel + AOI-area reporting | #15, #16, #17 |

Legacy source for each is cited in the first markdown cell of the notebook
(`legacy:ravi_dialog.py` functions / `legacy:modules/*.py`).
