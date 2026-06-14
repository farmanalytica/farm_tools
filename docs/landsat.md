# Landsat — Methodology

> This module turns the open Landsat archive into decision-ready imagery and
> vegetation time series over a user-defined area of interest (AOI). It draws
> on Landsat 7, 8 and 9 (USGS/NASA Collection 2) through Google Earth Engine,
> cloud-masks every scene, and offers two complementary products: a
> **15 m pan-sharpened true-colour image** built from Top-of-Atmosphere (TOA)
> reflectance, and **30 m spectral products** (vegetation indices and
> multispectral composites) built from atmospherically-corrected Surface
> Reflectance (SR). A multi-mission vegetation-index time series (a Satellite
> Image Time Series, or SITS) is produced alongside, summarising how the AOI's
> condition evolves across the full archive. This note describes the data and
> the science, not the software.

## 1. Objective

The goal is to give a researcher or land manager a faithful, analysis-ready
view of an area's surface condition over time, from a single map window:

1. **See the land at its sharpest.** Native Landsat optical bands are 30 m;
   pan-sharpening with the 15 m panchromatic band doubles the effective
   spatial detail of the true-colour image, useful for delineating field
   boundaries, roads, gaps and small features.
2. **Measure vegetation and water quantitatively.** Spectral indices computed
   on Surface Reflectance turn raw bands into physically interpretable numbers
   (greenness, water content, soil exposure).
3. **Track change.** A combined Landsat 7/8/9 index time series places any
   single date in the context of the whole record (1999 to present), revealing
   seasonality, trends, disturbances and recovery.

Every product is restricted to scenes that actually cover the AOI well and are
sufficiently cloud-free, so the user is never shown a date that is mostly
cloud or mostly outside the frame.

## 2. Data sources

All imagery comes from the **USGS Landsat Collection 2, Tier 1** archive,
accessed through Google Earth Engine. Tier 1 is the highest-quality tier:
scenes are radiometrically calibrated and co-registered to sub-pixel geometric
accuracy, which is the prerequisite for stacking dates into a time series.

| Sensor / Collection | Resolution | Temporal coverage | Bands used |
|---|---|---|---|
| **Landsat 7 ETM+** (`LANDSAT/LE07/C02/T1_L2` SR, `…/T1_TOA` TOA) | 30 m optical, 15 m panchromatic | 1999-04-15 → 2022-04-06 | blue, green, red, NIR, SWIR1, SWIR2, pan |
| **Landsat 8 OLI/TIRS** (`LANDSAT/LC08/C02/T1_L2`, `…/T1_TOA`) | 30 m optical, 15 m panchromatic | 2013-04-11 → present | blue, green, red, NIR, SWIR1, SWIR2, pan |
| **Landsat 9 OLI-2/TIRS-2** (`LANDSAT/LC09/C02/T1_L2`, `…/T1_TOA`) | 30 m optical, 15 m panchromatic | 2021-11-01 → present | blue, green, red, NIR, SWIR1, SWIR2, pan |

**Coverage and revisit.** Coverage is global. Each Landsat satellite revisits a
given location every **16 days**; because Landsat 8 and 9 are phased 8 days
apart, their combined revisit is effectively **8 days** for dates after late
2021, and adding Landsat 7 thickens the historical record back to 1999. A
request whose date range falls outside a given mission's lifespan simply
returns no scenes for that mission — there is no error, the other missions
still contribute.

**Landsat 5 is deliberately excluded.** The TM sensor on Landsat 5 carries no
panchromatic band, so the headline 15 m pan-sharpened product cannot be built
from it.

### Top-of-Atmosphere (TOA) vs. Surface Reflectance (SR)

Two physically different products are used, each for the job it suits best:

- **Surface Reflectance (SR, `T1_L2`).** Reflectance corrected for atmospheric
  scattering and absorption — i.e. an estimate of the reflectance *at the
  ground*. Stored as scaled integers, rescaled here to true reflectance with
  the official Collection 2 factors (multiply by 0.0000275, subtract 0.2),
  giving physical values in the 0–1 range. SR is the correct basis for
  **quantitative** work, so all vegetation indices and multispectral
  composites are computed on SR.
- **Top-of-Atmosphere (TOA, `T1_TOA`).** Reflectance as measured by the sensor,
  still including atmospheric effects. TOA is used for the **pan-sharpened
  true-colour image** because the panchromatic band is distributed in the TOA
  product, and pan-sharpening is a visual-enhancement step where absolute
  ground calibration matters less than spatial detail.

In short: **look at TOA (sharp, 15 m), measure on SR (calibrated, 30 m).**

## 3. Methodology

The processing chain is identical in spirit for every product; the steps below
are applied server-side in Earth Engine and only the finished result is
transferred.

### 3.1 Scene discovery

For the chosen AOI and date range, the archive is searched across all three
missions. Candidate scenes are filtered by spatial intersection with the AOI
and by acquisition date, then passed through the cloud mask and the
minimum-valid-coverage test (below). The surviving acquisition dates are
de-duplicated, tagged with their mission, and sorted chronologically, so the
user is offered only dates that yield a usable image over the AOI.

### 3.2 Cloud and quality masking

Clouds, shadows and other contaminated pixels are removed before anything is
measured or displayed. Two mechanisms are used:

- **QA_PIXEL bitmask (all products).** Every Collection 2 scene ships a
  per-pixel quality band. The mask removes pixels flagged as **cloud, cloud
  shadow, cirrus, dilated cloud, and saturated**, keeping only confidently
  clear pixels.
- **Simple Cloud Score (TOA only).** The pan-sharpened TOA product receives an
  additional pass: Earth Engine's Landsat Simple Cloud Score assigns each pixel
  a 0–100 cloud-likelihood, and pixels above a strictness threshold (default
  **15**, lower = stricter) are discarded. This suppresses bright haze that the
  bitmask alone can miss in the un-corrected TOA data.

Masking is on by default. Disabling it returns more dates but much noisier
imagery, and is only advisable when clouds are not a concern.

### 3.3 Minimum-valid-coverage filter

A scene can intersect the AOI yet still be useless if most of the AOI is masked
out (cloud) or simply lies outside the scene footprint. A
**minimum-valid-coverage** threshold (default **80 %**) guards against this: a
scene is kept only if the count of clear, in-AOI pixels reaches the requested
fraction of the pixels a fully-covered, cloud-free image would contain.

Because resolution differs between products, the same percentage corresponds to
a different absolute pixel count for the 15 m pan-sharpened image versus the
30 m SR products; the threshold is therefore evaluated per product against the
AOI's true (ellipsoidal) area. The *same* percentage governs the date list, the
time series and every download, so all three always agree on which dates are
"valid".

### 3.4 Pan-sharpening (HSV → 15 m)

The true-colour image is sharpened from 30 m to **15 m** using **HSV
(Hue–Saturation–Value) pan-sharpening** on the TOA product:

1. The 30 m red, green and blue bands are resampled to the 15 m grid of the
   panchromatic band.
2. The RGB triplet is converted from the RGB colour space to **HSV**, which
   separates *colour* (hue and saturation) from *brightness* (value).
3. The 15 m panchromatic band — which carries the fine spatial detail —
   **replaces the value (brightness) channel**.
4. The result is converted back to RGB.

The output therefore takes its **colour from the 30 m RGB** and its **spatial
detail from the 15 m pan band**, the standard HSV substitution that preserves
the scene's true colour while doubling apparent sharpness. The original cloud
mask is retained on the sharpened result.

### 3.5 Spectral indices (formulas)

Indices are computed pixel-by-pixel on **Surface Reflectance** (so band values
are physical 0–1 reflectances). Below, ρ denotes reflectance in a band
(ρ_NIR, ρ_red, ρ_green, ρ_blue, ρ_SWIR1). Fourteen indices are offered; none
require a red-edge band, because Landsat has no red-edge sensor.

**Greenness / vegetation vigour**

- **NDVI** — Normalized Difference Vegetation Index:

  NDVI = (ρ_NIR − ρ_red) / (ρ_NIR + ρ_red)

- **GNDVI** — Green NDVI (more sensitive to chlorophyll/canopy nitrogen):

  GNDVI = (ρ_NIR − ρ_green) / (ρ_NIR + ρ_green)

- **EVI** — Enhanced Vegetation Index (resists soil and atmosphere, does not
  saturate over dense canopy):

  EVI = 2.5 · (ρ_NIR − ρ_red) / (ρ_NIR + 6·ρ_red − 7.5·ρ_blue + 1)

- **EVI2** — two-band EVI (no blue band; robust where blue is noisy):

  EVI2 = 2.5 · (ρ_NIR − ρ_red) / (ρ_NIR + 2.4·ρ_red + 1)

**Soil-adjusted (for sparse cover / bare backgrounds)**

- **SAVI** — Soil-Adjusted Vegetation Index (L = 0.5):

  SAVI = 1.5 · (ρ_NIR − ρ_red) / (ρ_NIR + ρ_red + 0.5)

- **OSAVI** — Optimized SAVI:

  OSAVI = (ρ_NIR − ρ_red) / (ρ_NIR + ρ_red + 0.16)

- **MSAVI** — Modified SAVI (self-adjusting soil factor):

  MSAVI = ( 2·ρ_NIR + 1 − √[ (2·ρ_NIR + 1)² − 8·(ρ_NIR − ρ_red) ] ) / 2

**Atmosphere- and chlorophyll-sensitive**

- **ARVI** — Atmospherically Resistant Vegetation Index:

  ARVI = (ρ_NIR − (2·ρ_red − ρ_blue)) / (ρ_NIR + (2·ρ_red − ρ_blue))

- **CIgreen** — Green Chlorophyll Index:

  CIgreen = (ρ_NIR / ρ_green) − 1

- **CIred** — Red Chlorophyll Index:

  CIred = (ρ_NIR / ρ_red) − 1

- **MCARI** — Modified Chlorophyll Absorption in Reflectance Index:

  MCARI = [ (ρ_NIR − ρ_red) − 0.2·(ρ_NIR − ρ_green) ] · (ρ_NIR / ρ_red)

**Water and bare soil**

- **NDWI** — Normalized Difference Water Index (here the NIR/SWIR1 formulation,
  sensitive to vegetation/canopy water content):

  NDWI = (ρ_NIR − ρ_SWIR1) / (ρ_NIR + ρ_SWIR1)

- **MNDWI** — Modified NDWI (open-water delineation, green vs. SWIR1):

  MNDWI = (ρ_green − ρ_SWIR1) / (ρ_green + ρ_SWIR1)

- **BSI** — Bare Soil Index:

  BSI = [ (ρ_SWIR1 + ρ_red) − (ρ_NIR + ρ_blue) ] / [ (ρ_SWIR1 + ρ_red) + (ρ_NIR + ρ_blue) ]

### 3.6 Multispectral composites

For qualitative interpretation, three SR bands can be assigned to the red,
green and blue display channels. Four standard combinations are provided:

- **Real colour** (red·green·blue) — the scene as the eye would see it.
- **NIR · Red · Green** (colour-infrared) — healthy vegetation appears bright
  red; classic for vigour and crop/forest mapping.
- **SWIR1 · NIR · Red** — separates soil moisture, vegetation and bare ground;
  useful after fire or for senescence.
- **SWIR2 · NIR · Green** — emphasises burned areas, geology and moisture
  contrasts.

### 3.7 Vegetation-index time series (SITS)

Alongside the imagery, a **Satellite Image Time Series** of the chosen index is
built over the AOI. For each clear date that passes the coverage filter, the
index is reduced to a single representative value over the AOI — the spatial
**median** by default (robust to residual outliers), with **mean** available.
This is computed entirely server-side; no rasters are downloaded for the chart.

Each mission is queried only within the overlap of its own lifespan and the
requested range, then the three series (Landsat 7, 8, 9) are merged into one
chronological record and plotted as one trace per mission. Because the missions
share a common 30 m SR calibration, their values are directly comparable,
giving a continuous index history from 1999 to the present.

## 4. Outputs & interpretation

| Product | Basis | Resolution | Values / units |
|---|---|---|---|
| Pan-sharpened true-colour RGB | TOA | **15 m** | 3-band visual image |
| Vegetation index map | SR | 30 m | single band, dimensionless |
| Multispectral composite | SR | 30 m | 3-band false/true colour |
| Index time series (SITS) | SR | per-AOI value | one number per date |

**Pan-sharpened RGB (15 m).** The sharpest visual product. Read it as an
ordinary aerial-style photo: field boundaries, gaps, tracks and small
structures are resolved roughly twice as finely as in the native 30 m image.
Colours are TOA-based, so absolute tone may differ slightly from a
surface-corrected image; it is intended for *seeing*, not for measuring.

**Vegetation index maps.** Each pixel is a physical index value. The ratio
indices (NDVI, GNDVI, NDWI, MNDWI, ARVI, BSI) are **bounded to roughly −1…+1**:
for NDVI-type indices, bare soil and built-up surfaces sit near 0–0.2, sparse
or stressed vegetation around 0.2–0.4, and dense healthy canopy 0.6–0.9; water
is negative. The chlorophyll indices (CIgreen, CIred) and MCARI are
**unbounded ratios** that rise with canopy chlorophyll. SAVI/OSAVI/MSAVI track
NDVI but stay more reliable where vegetation is sparse and soil dominates.
BSI is positive over bare/exposed soil and negative over vegetation. Maps are
shown with a colour ramp (default red→yellow→green for greenness indices) so
that high values read as vigorous vegetation.

**Multispectral composites.** Interpret by band assignment (see 3.6) — e.g. in
colour-infrared, the brighter the red, the more vigorous the vegetation.

**Index time series.** The x-axis is acquisition date, the y-axis the AOI's
index value. Read it for **seasonal cycles** (crop green-up and senescence),
**multi-year trends** (gradual gain or loss of vegetation), and **abrupt
drops** (harvest, clearing, fire, flooding). Gaps mean no clear, well-covered
scene was available in that window. Different missions are colour-coded so any
cross-sensor offsets remain visible.

## 5. Limitations & caveats

- **Cloud cover** is the main limiter. In persistently cloudy or wet seasons,
  the coverage filter may leave few or no usable dates; loosening the threshold
  or the cloud mask trades data quantity for quality.
- **Landsat 7 SLC failure (post-2003-05-31).** The ETM+ scan-line corrector
  failed in 2003, leaving striped data gaps over roughly 22 % of every Landsat
  7 scene thereafter. For gapless post-2013 work, prefer Landsat 8/9.
- **TOA vs. SR mismatch.** The 15 m sharpened image is TOA (uncorrected), while
  indices and composites are SR. Do not compare absolute brightness between the
  sharpened RGB and the SR composites as if they were the same product.
- **Pan-sharpening is an enhancement, not new information.** HSV sharpening
  redistributes 30 m colour onto a 15 m brightness structure; it improves
  visual delineation but does not add true 15 m multispectral measurement.
- **Index physics.** NDVI and similar saturate over very dense canopy (use EVI,
  EVI2 or chlorophyll indices there) and are biased by soil where cover is
  sparse (use SAVI/OSAVI/MSAVI). The "NDWI" offered here is the NIR–SWIR1
  (canopy-water) form; for open-water mapping use MNDWI.
- **Mixed and edge pixels.** At 30 m, small or thin features blend with their
  surroundings; a narrow AOI may be dominated by mixed pixels.
- **Geometric / atmospheric residuals.** Even Tier 1 SR retains small
  georegistration and atmospheric-correction residuals; cross-mission
  time-series steps can reflect sensor differences rather than real change.
- **Resolution floor.** The finest product is 15 m. This module does not
  resolve sub-field detail finer than that.

## 6. References

- USGS / NASA Landsat Collection 2 Level-2 (Surface Reflectance) and Level-1
  (TOA) products; Landsat 7 ETM+, Landsat 8 OLI/TIRS, Landsat 9 OLI-2/TIRS-2.
- Collection 2 QA_PIXEL quality-assessment band and bitmask definitions (USGS).
- Earth Engine `ee.Algorithms.Landsat.simpleCloudScore` (Simple Cloud Score).
- HSV pan-sharpening: substitution of the intensity/value channel by the
  panchromatic band (standard component-substitution sharpening).
- Index literature: Rouse et al. (NDVI, 1974); Gitelson et al. (GNDVI,
  chlorophyll indices CIgreen/CIred); Huete et al. (EVI); Jiang et al. (EVI2);
  Huete (SAVI); Rondeaux et al. (OSAVI); Qi et al. (MSAVI); Kaufman & Tanré
  (ARVI); Daughtry et al. (MCARI); Gao (NDWI, NIR–SWIR); Xu (MNDWI);
  Rikimaru et al. (BSI).
- Data accessed via Google Earth Engine and the `agrigee_lite` Landsat wrapper.
