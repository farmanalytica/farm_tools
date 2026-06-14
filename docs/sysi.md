# SYSI (Synthetic Soil Image) — Methodology

> The Synthetic Soil Image (SYSI) is a cloud-free, vegetation-free reflectance
> image of the soil surface, synthesized from many years of satellite passes.
> Because a single satellite scene almost always shows a mixture of crops,
> pasture, stubble and bare ground, no one date reveals the soil everywhere.
> SYSI solves this by scanning a long multi-temporal Sentinel-2 archive,
> keeping only the pixels that are genuinely bare soil on each date, and then
> taking the per-pixel temporal **median** of those bare-soil observations. The
> result is a seamless 9-band, 10 m reflectance image of the exposed soil
> surface — a "best-ever look" at the ground beneath the vegetation. The
> bare-soil selection follows the **GEOS3** (Geospatial Soil Sensing System)
> spectral rule of Demattê et al. (2018).

## 1. Objective

Conventional soil maps and field sampling are sparse and expensive, yet the
soil surface itself carries a rich spectral signal: organic matter, iron
oxides, clay mineralogy, carbonates and moisture all leave fingerprints in the
visible, near-infrared and short-wave infrared reflectance. The problem is
*access*: at any given moment most fields are covered by crops or residue, so
the soil is only visible in scattered patches and on scattered dates.

The objective of SYSI is to **reconstruct a complete, stable image of the bare
soil reflectance** over an area of interest by exploiting the full temporal
depth of the Sentinel-2 archive. Every pixel is allowed to "show its soil" on
whichever dates it happened to be bare (fallow, freshly tilled, between crop
cycles), and those moments are combined into one synthetic image. This image
becomes the raw material for:

- **Digital soil mapping** — predicting clay, sand, organic carbon, iron and
  other attributes from the reflectance image.
- **Soil-class and management-zone delineation** — distinguishing soil bodies
  by their intrinsic colour and spectral behaviour rather than by current land
  cover.
- **Bare-soil reflectance libraries** — a calibrated surface-reflectance
  baseline that can be sampled, validated against field data, and compared
  across seasons and years.

## 2. Data sources

**Sensor and collection.** The image is built from the European Space Agency's
**Sentinel-2** mission, using the surface-reflectance product
*Sentinel-2 SR Harmonized*. This is an atmospherically corrected (bottom-of-
atmosphere) product, harmonized across the Sentinel-2A/2B processing baselines
so that scenes from different years are radiometrically comparable. Sentinel-2
revisits the same ground roughly every five days, which over several years
yields hundreds of looks at each pixel — the temporal richness SYSI depends on.

**Spatial resolution.** All outputs are produced at **10 m** ground sampling.

**Spectral bands used.** Seven optical bands are drawn from each scene, plus the
scene quality band used for cloud screening:

| Role in SYSI   | Sentinel-2 band | Centre wavelength (approx.) |
|----------------|-----------------|-----------------------------|
| Blue           | B2              | 490 nm                      |
| Green          | B3              | 560 nm                      |
| Red            | B4              | 665 nm                      |
| Red-edge 2     | B6              | 740 nm                      |
| NIR            | B8              | 842 nm                      |
| SWIR-1         | B11             | 1610 nm                     |
| SWIR-2         | B12             | 2190 nm                     |
| Cloud QA       | QA60            | (quality flags)             |

The visible (Blue/Green/Red) and red-edge bands respond strongly to soil colour
and iron oxides; the SWIR bands respond to clay minerals, carbonates and
moisture; the NIR band anchors the vegetation test. The QA60 quality band is
used only to remove clouds and is not part of the final image.

## 3. Methodology

The pipeline is run entirely on the cloud (Google Earth Engine) so that the
multi-year archive never has to be downloaded. Conceptually it proceeds in five
stages: assemble the archive, screen clouds, compute the diagnostic spectral
indices, apply the GEOS3 bare-soil rule pixel-by-pixel and date-by-date, then
collapse the surviving bare-soil pixels with a temporal median.

### 3.1 Archive assembly and user controls

The user defines an **area of interest (AOI)** and the following filters:

- A **date range** (the Sentinel-2 SR archive begins 2017-03-28; the default
  end is the current day).
- A **month selection** — any subset of the twelve calendar months. This lets
  the analyst restrict the search to the local fallow/tillage season, when soil
  is most likely exposed, and exclude the months of dense canopy.
- A **maximum cloud cover** per scene: scenes whose reported cloudy-pixel
  percentage exceeds this value are discarded outright.
- NDVI and NBR2 **threshold ranges** for the bare-soil rule (see §3.3).

Only scenes intersecting the AOI, falling inside the date range, within the
cloud limit, and tagged with a selected month are carried forward.

### 3.2 Cloud screening

Each surviving scene is masked with its **QA60** quality band. Pixels flagged
as **opaque cloud** (bit 10) or **cirrus** (bit 11) are removed before any
further processing, so that cloud tops and haze cannot contaminate the soil
signal.

### 3.3 Spectral indices and the GEOS3 bare-soil rule

For every pixel of every scene, four diagnostic quantities are computed. Two
are classic normalized-difference indices; two are simple slope differences
across the visible spectrum.

**NDVI — Normalized Difference Vegetation Index** (greenness):

```
NDVI = (NIR − Red) / (NIR + Red)
```

**NBR2 — Normalized Burn Ratio 2** (sensitive to dry/non-photosynthetic plant
material, i.e. crop residue and stubble):

```
NBR2 = (SWIR1 − SWIR2) / (SWIR1 + SWIR2)
```

**GRBL — Green-minus-Blue visible slope:**

```
GRBL = Green − Blue
```

**REGR — Red-minus-Green visible slope:**

```
REGR = Red − Green
```

**VNSIR — visible-to-near-infrared/SWIR tendency** (a composite shape term):

```
VNSIR = 1 − ( 2·Red − Green − Blue + 3·(NIR − Red) )
```

A pixel is accepted as **bare soil** only when **all** of the following
conditions hold simultaneously. Each criterion removes a specific class of
non-soil surface:

1. **NDVI within `[NDVI_min, NDVI_max]`** — *removes green vegetation.* Living
   canopy has high NDVI; bare soil has low NDVI. The accepted range is set by
   the analyst (a low band, near zero), keeping only weakly-vegetated to bare
   pixels.

2. **NBR2 within `[NBR2_min, NBR2_max]`** — *removes dry crop residue and
   non-photosynthetic vegetation.* NDVI alone cannot tell bare soil from
   senesced straw or stubble, because dead plant matter is not green. NBR2
   responds to the cellulose/lignin absorption between the two SWIR bands, so
   constraining it screens out fields that are merely covered in dry residue.

3. **VNSIR ≤ 0.9** — *enforces the spectral shape of soil across the
   visible-to-infrared range.* Soil reflectance rises gently and continuously
   from blue toward the infrared; vegetation and other surfaces produce a
   different curvature. The VNSIR term captures that overall tendency, and the
   **0.9** ceiling (a fixed constant in the GEOS3 formulation, not a user
   setting) rejects pixels whose spectral shape is inconsistent with bare soil.

4. **GRBL > 0  (Green > Blue)** — *first segment of the rising visible slope.*
   Bare soil characteristically reflects more in green than in blue. Surfaces
   that violate this (e.g. water, shadow, some vegetation) are rejected.

5. **REGR > 0  (Red > Green)** — *second segment of the rising visible slope.*
   Bare soil continues to brighten from green to red. Requiring both GRBL > 0
   and REGR > 0 enforces the monotonic blue → green → red increase that is the
   visible signature of exposed soil, while excluding the green peak of
   vegetation.

Note that the GRBL/REGR sign tests are scale-invariant (Green > Blue is true
regardless of reflectance units), so only the NDVI, NBR2 and VNSIR tests depend
on the optical bands being scaled to surface reflectance in the [0–1] range,
which the pipeline applies before the rule is evaluated.

Pixels passing all five conditions are retained; everything else (including
residual negative-valued no-data pixels at scene black borders) is masked out
on that date.

### 3.4 Temporal median composite

After the rule is applied to every scene, each pixel holds a *stack* of
bare-soil reflectance values — one for each date on which it was bare and
cloud-free — and gaps wherever it was vegetated, cloudy or otherwise rejected.
The stack is collapsed by taking the **per-pixel temporal median** of the
surviving observations.

The median is chosen deliberately. It is robust to the occasional outlier
(a thin cloud the QA band missed, a transiently wet or freshly-tilled surface)
and, because it is computed independently per pixel, it naturally **fills gaps**:
a pixel that was bare in only a handful of scenes still contributes its median,
and neighbouring pixels that were bare on entirely different dates are stitched
into one continuous surface. The outcome is a single, spatially complete image
representing the typical bare-soil reflectance of each location.

### 3.5 Output composition

The composite is reduced to **nine bands** and clipped to the AOI:

```
Blue · Green · Red · Rededge2 · NIR · SWIR1 · SWIR2 · NDVI · NBR2
```

— the seven surface-reflectance bands plus the two diagnostic indices — exported
at **10 m** as a single floating-point image.

## 4. Outputs & interpretation

**The synthetic soil image.** The deliverable is one 9-band, 10 m raster of
bare-soil surface reflectance covering the whole AOI, with band names embedded
in the file. Unlike a single satellite scene, it contains no clouds, no crops
and no residue — it is the synthesized soil surface.

**Natural-colour view.** Displayed as a true-colour composite (Red on the red
channel, Green on green, Blue on blue), the image reads like an aerial photo of
the bare ground: it shows the soil's actual colour. Reddish tones typically
indicate iron-oxide-rich, well-drained soils; yellow-brown tones often relate to
goethite and intermediate drainage; dark tones commonly correspond to higher
organic-matter or moister soils; pale, bright tones suggest sandy, carbonate-
rich or eroded surfaces where subsoil is exposed. These colour patterns
frequently follow toposequences and parent-material boundaries, making the image
immediately legible to an experienced soil scientist.

**Agronomic and pedological use.** Because every pixel is a calibrated
reflectance spectrum sampled across the visible–NIR–SWIR range, the image
supports quantitative work:

- Predicting **clay, sand, organic carbon and iron** content via spectral
  models calibrated to field samples.
- Mapping **soil classes and parent materials**, and delineating
  **management zones** for variable-rate fertility, liming and sampling design.
- Targeting **field sampling** to spectrally distinct areas, reducing the number
  of samples needed for a reliable map.
- Detecting **erosion and exposed subsoil**, which appear as anomalously bright
  or differently coloured patches.

## 5. Limitations & caveats

- **Bare-soil opportunity is required.** SYSI can only characterise a pixel that
  was actually exposed at least once in the chosen period. Permanent pasture,
  forest, perennial orchards and continuously cropped fields may yield few or no
  valid observations, leaving sparse or empty areas.
- **Surface, not depth.** The reflectance describes only the top few millimetres
  of soil. Crusting, recent tillage, surface mulch and stone cover can bias the
  signal relative to the bulk topsoil.
- **Residual moisture and roughness.** The median suppresses, but does not fully
  remove, the influence of soil moisture and surface roughness, which darken and
  flatten spectra. Restricting the month selection to a dry fallow season
  mitigates this.
- **Threshold sensitivity.** The NDVI and NBR2 ranges are user-set. Bands that
  are too permissive admit sparse vegetation or residue; bands too strict
  discard valid soil and shrink coverage. The VNSIR ceiling (0.9) is fixed and
  not tuned per site.
- **Mixed and composite dates.** Each pixel's value is a temporal median across
  potentially many years and conditions; it is a *typical* bare-soil reflectance,
  not the state on any single date.
- **Imperfect cloud screening.** The QA60 mask can miss thin cirrus or haze; the
  median's robustness is the main safeguard against such leakage.
- **Calibration still required.** Reflectance values are not soil attributes.
  Quantitative maps (clay, carbon, etc.) require local field samples and a
  fitted spectral model; transferring a model across regions without
  recalibration is risky.

## 6. References

- Demattê, J. A. M., Fongaro, C. T., Rizzo, R., & Safanelli, J. L. (2018).
  *Geospatial Soil Sensing System (GEOS3): A powerful data mining procedure to
  retrieve soil spectral reflectance from satellite images.* Remote Sensing of
  Environment, 212, 161–175. https://doi.org/10.1016/j.rse.2018.04.047
- European Space Agency / Copernicus. *Sentinel-2 MSI Level-2A (Surface
  Reflectance) product.* Sentinel-2 SR Harmonized collection.
- Rouse, J. W., Haas, R. H., Schell, J. A., & Deering, D. W. (1974).
  *Monitoring vegetation systems in the Great Plains with ERTS* — origin of the
  NDVI index.
- Key, C. H., & Benson, N. C. (2006). *Landscape assessment: ground measure of
  severity, the Composite Burn Index; and remote sensing of severity, the
  Normalized Burn Ratio* — background to the NBR/NBR2 family of indices.
