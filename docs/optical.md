# Optical (Sentinel-2) — Methodology

> This document describes how the Optical tool turns the Sentinel-2 surface-reflectance archive into a vegetation-index analysis for a chosen area of interest (AOI). For a date range and a spectral index, the tool builds one cloud-screened scene per acquisition date, computes the AOI-average index, and produces an interactive time series. From that series the user can smooth the signal, overlay rainfall, sample individual points or fields, render single-date imagery, and integrate the index through time into a single composite map. The emphasis throughout is on consistent, reproducible cloud masking so that every product — plot, point series, and composite — reflects the same clear-sky pixels.

## 1. Objective

Vegetation condition, water content, and canopy structure all leave a fingerprint in reflected sunlight. The goal of this tool is to make that fingerprint quantitative and trackable over time for a specific area: a field, a farm, a watershed, or a single sampling point. Concretely it answers questions such as:

- How has greenness (or any of 19 spectral indices) evolved across a growing season?
- Which dates are clear enough to trust, and which are contaminated by cloud or shadow?
- How does one field compare to its neighbours, or one sampling point to the field average?
- What does the season look like as a single integrated map (mean, peak, or area-under-the-curve)?

All processing runs on Google Earth Engine, so the analysis works at any scale without the user downloading the full image archive.

## 2. Data sources

### 2.1 Sentinel-2 Surface Reflectance (Harmonized)

The tool reads the **`COPERNICUS/S2_SR_HARMONIZED`** collection — Sentinel-2 Level-2A bottom-of-atmosphere (surface) reflectance, atmospherically corrected and **harmonized** so that scenes processed before and after the January 2022 processing-baseline change (which introduced a radiometric offset) form one continuous, comparable archive. Reflectance is stored as scaled integers (digital numbers); dividing by **10000** converts a band to physical reflectance in the 0–1 range, which is the form all index formulas below assume.

Sentinel-2 is a two-satellite constellation (Sentinel-2A and -2B) in a sun-synchronous orbit.

| Band | Name | Centre (nm) | Native resolution |
|------|------|-------------|-------------------|
| B1  | Coastal aerosol      | 443  | 60 m |
| B2  | Blue                 | 490  | 10 m |
| B3  | Green                | 560  | 10 m |
| B4  | Red                  | 665  | 10 m |
| B5  | Red Edge 1           | 705  | 20 m |
| B6  | Red Edge 2           | 740  | 20 m |
| B7  | Red Edge 3           | 783  | 20 m |
| B8  | NIR (broad)          | 842  | 10 m |
| B8A | NIR (narrow)         | 865  | 20 m |
| B9  | Water vapour         | 945  | 60 m |
| B11 | SWIR 1               | 1610 | 20 m |
| B12 | SWIR 2               | 2190 | 20 m |
| SCL | Scene Classification | —    | 20 m |

(Band B10, the cirrus band, carries no surface information and is absent from the Level-2A surface-reflectance product.)

- **Coverage:** global land surfaces and coastal waters.
- **Revisit:** roughly every 5 days at the equator with both satellites combined, more frequent at higher latitudes where adjacent orbit swaths overlap. In practice a given AOI yields a usable scene every few days, weather permitting.
- **Tiling:** scenes are delivered on a fixed 100 × 100 km military-grid (MGRS) tile scheme. An AOI that straddles two tiles can appear in more than one scene per date.

### 2.2 Rainfall (optional overlay)

For context, daily/monthly precipitation can be drawn from the **NASA POWER** climate reanalysis over the same AOI and date range, plotted as bars beneath the index curve. This is an overlay only and does not enter the index computation.

## 3. Methodology

### 3.1 Scene selection and one-scene-per-date deduplication

The archive is first restricted to scenes that intersect the AOI bounding box within the chosen date range. Because the AOI may sit near a tile boundary or be revisited by overlapping orbits, **more than one image can exist for the same calendar date**. Carrying all of them would double-count dates and bias the time series, so the tool keeps exactly **one image per acquisition date**, chosen by a simple score:

> **score = (AOI footprint coverage) − (tile cloudiness)**

where coverage is the fraction of the AOI actually covered by the image footprint (dominant term) and cloudiness is the scene-level `CLOUDY_PIXEL_PERCENTAGE` metadata normalized to 0–1 (tie-breaker). The image with the highest score on each date wins. The intent: prefer the scene that covers the most of your area, and among equally complete scenes prefer the clearest. Footprint coverage uses the nominal tile geometry, so it mainly distinguishes AOIs that span multiple tiles rather than partial-swath edge effects within a single tile.

### 3.2 Cloud and shadow masking (Scene Classification Layer)

Every Sentinel-2 Level-2A scene ships with a per-pixel **Scene Classification Layer (SCL)** assigning each 20 m pixel to one of 12 classes:

| Value | Class | Treated as invalid by default |
|-------|-------|:--:|
| 0  | No data | yes |
| 1  | Saturated / defective | yes |
| 2  | Dark area / shadow pixels | yes |
| 3  | Cloud shadow | yes |
| 4  | Vegetation | no |
| 5  | Bare soil | no |
| 6  | Water | no |
| 7  | Unclassified | no |
| 8  | Cloud, medium probability | yes |
| 9  | Cloud, high probability | yes |
| 10 | Thin cirrus | yes |
| 11 | Snow / ice | no |

The user selects which classes count as "invalid" (clouds, shadows, defects, and cirrus are pre-checked). This drives two things:

1. **Clear-pixel accounting (always on).** For each kept scene the tool counts SCL-valid pixels versus total pixels inside the AOI, at 10 m, giving a **valid-pixel percentage** — the local, in-AOI measure of how clear that date really is. This number is reported per date regardless of whether masking is applied, so the user can judge data quality.
2. **Pixel masking (optional).** When "Apply SCL mask" is enabled, the invalid classes are removed from every scene *before* the index is computed, so cloud and shadow pixels never contaminate the index, the time series, or any downloaded raster.

Because masking changes which pixels feed the index, it is fixed at the start of an analysis and then **replayed identically** for the time series, the point/feature sampling, and the composite — guaranteeing that all derived products describe the same clear-sky observations.

### 3.3 Spectral index registry

For each kept, optionally masked scene the tool computes one chosen spectral index, reducing the multiband image to a single `index` band. Nineteen indices are built in. In the formulas below, band symbols denote **surface reflectance in 0–1** (i.e. raw band ÷ 10000); for the normalized-difference indices the scaling cancels and is immaterial.

**Broadband greenness / vegetation vigour**

- **NDVI** — Normalized Difference Vegetation Index
  $$\mathrm{NDVI}=\frac{\mathrm{NIR}-\mathrm{Red}}{\mathrm{NIR}+\mathrm{Red}}=\frac{B8-B4}{B8+B4}$$
- **GNDVI** — Green NDVI (more sensitive to chlorophyll than NDVI)
  $$\mathrm{GNDVI}=\frac{B8-B3}{B8+B3}$$
- **EVI** — Enhanced Vegetation Index (reduces soil and atmosphere effects, resists saturation in dense canopy)
  $$\mathrm{EVI}=2.5\cdot\frac{\mathrm{NIR}-\mathrm{Red}}{\mathrm{NIR}+6\,\mathrm{Red}-7.5\,\mathrm{Blue}+1}$$
- **EVI2** — two-band EVI (no blue band, less noise-prone)
  $$\mathrm{EVI2}=2.5\cdot\frac{\mathrm{NIR}-\mathrm{Red}}{\mathrm{NIR}+\mathrm{Red}+1}$$
- **SAVI** — Soil-Adjusted Vegetation Index (soil-brightness correction, $L=0.5$)
  $$\mathrm{SAVI}=(1+L)\cdot\frac{\mathrm{NIR}-\mathrm{Red}}{\mathrm{NIR}+\mathrm{Red}+L}$$
- **MSAVI** — Modified SAVI (self-adjusting soil factor, no external $L$)
  $$\mathrm{MSAVI}=\frac{(2\,\mathrm{NIR}+1)-\sqrt{(2\,\mathrm{NIR}+1)^2-8(\mathrm{NIR}-\mathrm{Red})}}{2}$$
- **ARVI** — Atmospherically Resistant Vegetation Index (blue band corrects red for haze)
  $$\mathrm{ARVI}=\frac{\mathrm{NIR}-(2\,\mathrm{Red}-\mathrm{Blue})}{\mathrm{NIR}+(2\,\mathrm{Red}-\mathrm{Blue})}$$
- **VARI** — Visible Atmospherically Resistant Index (visible-only, useful for RGB-only context)
  $$\mathrm{VARI}=\frac{\mathrm{Green}-\mathrm{Red}}{\mathrm{Green}+\mathrm{Red}-\mathrm{Blue}}$$
- **TVI** — Triangular Vegetation Index (canopy chlorophyll / green biomass)
  $$\mathrm{TVI}=0.5\,\big(120(\mathrm{NIR}-\mathrm{Green})-200(\mathrm{Red}-\mathrm{Green})\big)$$
- **SFDVI** — Spectral Four-band Difference Vegetation Index
  $$\mathrm{SFDVI}=\frac{\mathrm{NIR}+\mathrm{Green}}{2}-\frac{\mathrm{Red}+\mathrm{RedEdge}}{2}$$

**Chlorophyll / red-edge sensitive**

- **CIgreen** — Green Chlorophyll Index
  $$\mathrm{CI_{green}}=\frac{\mathrm{NIR}}{\mathrm{Green}}-1=\frac{B8}{B3}-1$$
- **NDRE** — Normalized Difference Red Edge (canopy chlorophyll, penetrates dense canopy)
  $$\mathrm{NDRE}=\frac{B8-B5}{B8+B5}$$
- **ReCI** — Red-Edge Chlorophyll Index
  $$\mathrm{ReCI}=\frac{\mathrm{NIR}}{\mathrm{RedEdge}}-1=\frac{B8}{B5}-1$$
- **MTCI** — MERIS Terrestrial Chlorophyll Index
  $$\mathrm{MTCI}=\frac{\mathrm{NIR}-\mathrm{RedEdge}}{\mathrm{RedEdge}-\mathrm{Red}}=\frac{B8-B5}{B5-B4}$$
- **MCARI** — Modified Chlorophyll Absorption in Reflectance Index (here using NIR in the red-edge role)
  $$\mathrm{MCARI}=\big[(\mathrm{RE}-\mathrm{Red})-0.2(\mathrm{RE}-\mathrm{Green})\big]\cdot\frac{\mathrm{RE}}{\mathrm{Red}}$$
- **SIPI** — Structure-Insensitive Pigment Index (carotenoid : chlorophyll ratio)
  $$\mathrm{SIPI}=\frac{\mathrm{NIR}-\mathrm{Blue}}{\mathrm{NIR}-\mathrm{Red}}$$

**Water / moisture / burn**

- **NDMI** — Normalized Difference Moisture Index (vegetation water content)
  $$\mathrm{NDMI}=\frac{B8-B11}{B8+B11}$$
- **NDWI** — Normalized Difference Water Index (open-water / canopy water, green–NIR form)
  $$\mathrm{NDWI}=\frac{B3-B8}{B3+B8}$$
- **NBR** — Normalized Burn Ratio (fire severity, post-burn recovery)
  $$\mathrm{NBR}=\frac{B8-B12}{B8+B12}$$

**Custom indices.** A user may define additional indices as free-form band expressions (e.g. `(B8 - B4) / (B8 + B4 + 0.5)`). Only the twelve band tokens and arithmetic operators are permitted; the expression is validated for safety and syntax before use, and each band is divided by 10000 so the expression operates in 0–1 reflectance. Saved custom indices are stored for reuse.

### 3.4 AOI time series

For each kept scene the index is averaged over the AOI using a **10 m spatial mean** (`reduceRegion` with the mean reducer at 10 m scale). This produces one row per acquisition date:

- the **AOI-average index value**,
- **tile cloudiness** (scene-level `CLOUDY_PIXEL_PERCENTAGE`),
- the **in-AOI valid-pixel percentage** (§3.2),
- the **AOI footprint coverage** percentage.

Dates whose AOI average is undefined (e.g. fully masked) are dropped. The result is an index-versus-date time series describing how the chosen index evolved across the AOI.

Once computed, the series is held in memory: the user can re-screen it by **cloud / valid-pixel / coverage thresholds** (defaults: tile cloud ≤ 40%, valid pixels ≥ 80%, AOI coverage ≥ 90%) or toggle individual dates on and off, and the plot updates immediately. These quality filters change only which dates are displayed and exported — they do not alter the underlying pixels, so no recomputation is needed. Changing the masking or the date range, which *do* change the pixels, requires a fresh analysis.

### 3.5 Smoothing

Index time series are noisy: residual haze, view-angle differences, and partial clouds add scatter. An optional **Savitzky-Golay filter** fits a low-order polynomial in a moving window over the (date-sorted, quality-filtered) series, producing a smoothed curve that preserves the timing and amplitude of seasonal peaks better than a simple moving average. The window length is automatically constrained to be odd and no longer than the series, and the polynomial order is kept below the window length. Smoothing is a display-and-export transform only; it does not change the measured values.

### 3.6 Rainfall overlay

Monthly precipitation totals from NASA POWER can be drawn as bars beneath the index curve over the same period and AOI, placed mid-month against the daily axis. This is purely for visual context — for instance, relating a green-up to the onset of the rains.

### 3.7 Point and per-feature statistics

Beyond the single AOI average, the tool extracts index series for finer geometries, reusing the exact date range, index, masking, and custom expression of the main analysis so curves remain directly comparable:

- **Point sampling.** Clicking a location extracts the value of the **single 10 m pixel** under the click (the "first" reducer), which is truer to a ground sample than averaging a buffered disc. Each clicked point appears as its own line as soon as it is computed.
- **Per-feature series.** Each polygon feature of the AOI layer yields its own series, computed as the **polygon mean**, labelled by a chosen attribute field. This compares fields or management zones side by side.

For points and features the one-scene-per-date deduplication falls back to **lowest cloud cover** alone, because footprint coverage is meaningless for a zero-area geometry. All per-geometry curves are plotted against the AOI-average curve as a grey reference line.

### 3.8 Single-date imagery (RGB and index rasters)

For any date in the series the tool can render imagery into QGIS, clipped to the AOI (optionally grown or cropped by a buffer of up to ±300 m), exported as 10 m GeoTIFF in geographic coordinates (EPSG:4326):

- **RGB / false-colour composite** — the multispectral surface-reflectance stack, displayed under a chosen band combination (true colour B4/B3/B2 by default, plus NIR and SWIR false-colour presets), with a 2–98% per-band contrast stretch.
- **Single-index raster** — the chosen index as a continuous pseudocolour map (red-yellow-green by default).

### 3.9 Area-under-the-curve and composite maps

Finally the time dimension can be collapsed into a single map. Using only the dates currently displayed (after quality filtering), the index collection is reduced **pixel-by-pixel** to one composite raster by a chosen statistic:

- **Mean, Median, Min, Max** — central tendency or extremes of the index over the period;
- **Amplitude** — max − min, a measure of seasonal dynamic range;
- **Standard deviation** — temporal variability;
- **Sum** — accumulated index;
- **Area Under Curve (AUC)** — the index integrated over time.

The AUC uses the **trapezoidal rule**: acquisition dates are converted to day-offsets $t_i$, and for each pixel consecutive index values $v_i$ are integrated as

$$\mathrm{AUC}=\sum_{i=1}^{n-1}\frac{(v_i+v_{i+1})}{2}\,(t_{i+1}-t_i),$$

which approximates the area beneath the index-versus-time curve and is a robust proxy for cumulative productivity or biomass over the season. AUC is computed only on pixels that are valid on *every* contributing date, so the integral is built from a consistent stack. The composite is masked to the exact AOI, named by index and statistic, and rendered as a pseudocolour raster.

A **batch download** option additionally exports the full multispectral scene of every displayed date for offline use.

## 4. Outputs and interpretation

- **Index time series (the primary output).** A curve of the AOI-average index against date. Rising NDVI/EVI/SAVI indicates green-up (emergence, leaf expansion); a plateau marks peak canopy; a decline marks senescence, harvest, or stress. Each point carries quality metadata (cloud, valid-pixel %, coverage) so suspect dates can be screened out.
- **Index ranges.** Normalized-difference indices (NDVI, GNDVI, NDRE, NDMI, NBR, NDWI) are bounded in −1…+1; for healthy green vegetation NDVI typically falls in ~0.3–0.9, bare soil near 0.1–0.2, and water below 0. Ratio and structural indices (EVI, CIgreen, ReCI, MTCI, TVI, etc.) are not bounded to that range and are best read relatively — trends and contrasts rather than absolute thresholds.
- **Valid-pixel percentage.** The most reliable per-date quality flag: it measures clear pixels *inside your AOI*, unlike tile cloudiness which describes the whole 100 km scene. Low valid-pixel dates should be treated with caution even if tile cloud looks low.
- **Smoothed curve.** The de-noised seasonal trajectory; use it to read phenology (start/peak/end of season) rather than individual-date values.
- **Point / feature series.** Within-AOI heterogeneity — which point or field leads or lags the average, and by how much.
- **Single-date rasters.** Where in space the index is high or low on a given day; RGB for visual interpretation, index raster for quantitative patterns.
- **Composite / AUC maps.** A single season-summarizing map. Mean shows typical condition; amplitude and standard deviation highlight the most dynamic or variable areas; AUC approximates cumulative growth and is well suited to ranking productivity across a field.

## 5. Limitations and caveats

- **Cloud is the dominant constraint.** In persistently cloudy regions or seasons, usable dates can be sparse and unevenly spaced, which weakens smoothing and biases the AUC integral (the trapezoidal rule assumes the index between two observed dates is roughly linear — large gaps violate this).
- **SCL is imperfect.** The classifier misses thin cloud edges and faint shadows and occasionally flags bright bare soil or snow. Residual contamination can survive masking; conversely, aggressive masking removes valid pixels. The valid-pixel percentage helps detect both.
- **Mixed pixels and scale.** Index statistics are computed at 10 m. Indices that natively rely on 20 m bands (red-edge, SWIR) are resampled; very small AOIs or narrow features may contain few independent pixels.
- **Footprint coverage is tile-based.** Coverage uses the nominal MGRS tile geometry, so it reliably flags multi-tile AOIs but does not capture partial-swath gaps within a single tile.
- **Atmospheric residuals.** Surface reflectance is atmospherically corrected but not perfect; haze and aerosol still add scatter, which is why atmospherically resistant indices (ARVI, VARI) and de-noising exist. Compare relative trends rather than over-interpreting small absolute differences between single dates.
- **Index choice matters.** No single index is universally best. NDVI saturates in dense canopy (prefer EVI/EVI2 or red-edge indices); soil-adjusted indices (SAVI/MSAVI) suit sparse cover; red-edge and chlorophyll indices track nitrogen/chlorophyll; moisture and burn indices answer different questions entirely.
- **Rainfall overlay is coarse.** NASA POWER is a global reanalysis at ~0.5° resolution and provides regional context only, not field-scale rainfall.

## 6. References

- Drusch, M. et al. (2012). *Sentinel-2: ESA's Optical High-Resolution Mission for GMES Operational Services.* Remote Sensing of Environment, 120, 25–36.
- European Space Agency. *Sentinel-2 User Handbook* and *Level-2A Algorithm Theoretical Basis Document (Scene Classification).*
- Gorelick, N. et al. (2017). *Google Earth Engine: Planetary-scale geospatial analysis for everyone.* Remote Sensing of Environment, 202, 18–27.
- Rouse, J. W. et al. (1974). *Monitoring vegetation systems in the Great Plains with ERTS.* (NDVI.)
- Huete, A. R. (1988). *A soil-adjusted vegetation index (SAVI).* Remote Sensing of Environment, 25, 295–309.
- Qi, J. et al. (1994). *A modified soil adjusted vegetation index (MSAVI).* Remote Sensing of Environment, 48, 119–126.
- Huete, A. et al. (2002). *Overview of the radiometric and biophysical performance of the MODIS vegetation indices (EVI).* Remote Sensing of Environment, 83, 195–213.
- Gitelson, A. A. et al. (1996, 2003). *Green and red-edge chlorophyll indices (GNDVI, CIgreen).* Journal of Plant Physiology / Remote Sensing of Environment.
- Kaufman, Y. J. & Tanré, D. (1992). *Atmospherically Resistant Vegetation Index (ARVI).* IEEE TGRS, 30, 261–270.
- Dash, J. & Curran, P. J. (2004). *The MERIS terrestrial chlorophyll index (MTCI).* International Journal of Remote Sensing, 25, 5403–5413.
- Daughtry, C. S. T. et al. (2000). *MCARI: Estimating corn leaf chlorophyll concentration from leaf and canopy reflectance.* Remote Sensing of Environment, 74, 229–239.
- Gao, B. C. (1996). *NDWI — A normalized difference water index for remote sensing of vegetation liquid water.* Remote Sensing of Environment, 58, 257–266.
- Key, C. H. & Benson, N. C. (2006). *Landscape assessment: the Normalized Burn Ratio (NBR).* USGS.
- Savitzky, A. & Golay, M. J. E. (1964). *Smoothing and differentiation of data by simplified least squares procedures.* Analytical Chemistry, 36, 1627–1639.
- NASA POWER Project. *Prediction Of Worldwide Energy Resources.* https://power.larc.nasa.gov/
