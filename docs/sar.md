# SAR (Sentinel-1) — Methodology

> This module turns the Copernicus Sentinel-1 C-band radar archive into an
> analysis-ready backscatter time series over a chosen area of interest (AOI).
> Raw Ground Range Detected (GRD) scenes are passed through a standard
> Analysis-Ready Data (ARD) pipeline — additional border-noise removal, speckle
> filtering, and radiometric terrain flattening — and delivered as VV/VH
> backscatter in decibels. From the dual-polarization backscatter, nine
> radar vegetation/structure indices are derived, and the AOI-average of any
> chosen index (or raw polarization) is plotted as a dense, weather-independent
> time series. Because radar penetrates cloud and works day or night, the
> resulting series is continuous in a way optical (Sentinel-2/Landsat) data
> cannot match, making it well suited to monitoring crop growth, soil moisture,
> flooding, and structural change.

## 1. Objective

The goal is to provide a robust, cloud-free record of land-surface
**backscatter** through time, and to translate that backscatter into
interpretable vegetation and structure indices. Optical vegetation indices
(NDVI and similar) fail whenever clouds, smoke, or night intervene; in tropical
and humid regions this can mean weeks or months of missing data. Radar measures
the strength of the microwave echo returned from the surface, which depends on
surface roughness, geometry, and moisture rather than reflected sunlight. This
module therefore complements optical monitoring with an all-weather, all-season
signal that responds directly to canopy structure, biomass, and water content.

## 2. Data sources

**Mission.** [Sentinel-1](https://sentinel.esa.int/web/sentinel/missions/sentinel-1)
is a constellation of C-band Synthetic Aperture Radar (SAR) satellites operated
by the European Space Agency under the Copernicus programme. SAR is an *active*
sensor: it emits its own microwave pulses and records the backscattered echo, so
it is independent of solar illumination and largely transparent to clouds and
rain.

**Product.** The module uses the **Ground Range Detected (GRD)** product in
**Interferometric Wide (IW)** swath mode — the standard land-monitoring mode —
accessed in floating-point form through Google Earth Engine.

| Property | Value |
|---|---|
| Frequency band | C-band (~5.405 GHz, ~5.6 cm wavelength) |
| Polarizations (over land, IW) | VV and VH (dual-pol) |
| Spatial resolution | ~10 m (pixel spacing 10 m) |
| Swath width | ~250 km |
| Revisit | ~6–12 days at the equator (constellation-dependent), much denser at high latitudes |
| Coverage | Global, systematic acquisition |
| Orbit used here | **Descending** pass (fixed, so all scenes in a series share one viewing geometry) |

**Polarization.** A C-band SAR transmits and receives in horizontal (H) or
vertical (V) polarization. Sentinel-1 over land transmits vertically and
records both co-polarized (**VV**, vertical transmit / vertical receive) and
cross-polarized (**VH**, vertical transmit / horizontal receive) returns. VV is
sensitive mostly to surface scattering (bare soil, water, surface roughness)
while VH responds to **volume scattering** inside vegetation canopies, which is
why the ratio and difference of the two carry useful structural information.

**Why fix the orbit.** Backscatter depends on the radar's incidence angle and
look direction. Mixing ascending and descending passes in one time series
introduces geometry-driven steps that are easily mistaken for real change. The
module fixes the orbit to descending so that every observation in a series is
directly comparable.

## 3. Methodology

### 3.1 Analysis-Ready Data (ARD) pipeline

Raw GRD scenes are not directly comparable through time: they contain edge
artefacts, the characteristic SAR "speckle," and brightness variations caused
purely by terrain. The module standardizes them following the widely used
Sentinel-1 ARD framework of **Mullissa et al. (2021)**, which applies three
corrections in sequence. Each correction is independently switchable, and all
three are enabled by default.

**1. Border-noise removal.** Along the edges of each SAR scene, very low and
very high incidence angles produce spurious low-intensity returns and ragged
borders. This step masks out pixels whose incidence angle falls outside the
reliable range (roughly 30.6°–45.2°), discarding the noisy scene margins so they
do not contaminate AOI statistics. (Adapted from Hird et al., 2017.)

**2. Speckle filtering.** SAR images are inherently grainy: coherent
interference of the many scatterers within a resolution cell produces a
salt-and-pepper texture called *speckle*, which is multiplicative noise, not real
surface variation. The module suppresses it with a **multi-temporal Gamma-MAP
filter** by default. The Gamma Maximum-A-Posteriori estimator (Lopes et al.,
1990) adaptively smooths homogeneous areas while preserving edges and strong
point scatterers; the multi-temporal framework (Quegan & Yu, 2001) borrows
information from neighbouring acquisitions of the same orbit so that smoothing
does not blur true spatial detail. Other classical filters (Lee, Refined Lee,
Lee-Sigma, Boxcar) are available within the same framework.

**3. Radiometric terrain flattening.** On sloped terrain, the projected pixel
area — and hence the measured backscatter — changes with the angle between the
radar beam and the ground, so identical land cover looks brighter on
slopes facing the sensor and darker on slopes facing away. Terrain flattening
performs **radiometric terrain normalization**, converting the signal to
terrain-flattened **gamma-naught (γ⁰)** using a digital elevation model (SRTM by
default) and an angular slope-correction model (Vollrath et al., 2020). The
default *volume* model is appropriate for vegetated surfaces, where scattering
occurs throughout the canopy volume. This makes backscatter comparable across
flat and hilly parts of the same AOI.

**Output scaling.** After correction, backscatter is delivered in **decibels
(dB)** — a logarithmic scale, `dB = 10·log₁₀(linear power)` — or, optionally,
in **linear power**. The dB scale compresses the very wide dynamic range of
radar returns into an interpretable range (typically about −25 dB to +5 dB over
land) and is the standard for visualization and time-series analysis. A few
indices that involve products or square roots (notably DPSVIm) are formulated
for *linear* input; the in-app index help flags this.

### 3.2 Dual-polarization indices

From the VV and VH backscatter, the module computes nine dual-pol indices. Each
combines the surface-dominated VV channel and the volume-dominated VH channel to
emphasize vegetation density, canopy structure, or change. (Symbols `VV` and
`VH` below denote the corrected backscatter in the chosen output scale.)

| Index | Formula | Emphasis |
|---|---|---|
| **VV/VH Ratio** | `VV / VH` | Relative surface-vs-volume scattering |
| **RVI** (Radar Vegetation Index) | `4·VH / (VV + VH)` | Canopy randomness / vegetation density |
| **DpRVI** (Dual-pol RVI) | `VH / (VH + VV)` | Vegetation fraction, bounded 0–1 |
| **CR** (Cross Ratio) | `VH / VV` | Volume scattering strength |
| **NDPI** (Normalized Diff. Pol. Index) | `(VV − VH) / (VV + VH)` | Normalized contrast between channels |
| **PD** (Polarization Difference) | `VV − VH` | Absolute surface-vs-volume gap |
| **DPSVIm** (Modified Dual-pol SAR Veg. Index) | `VV·(VV + VH) / √2` | Combined intensity (linear input) |
| **PRVI** (Polarimetric RVI) | `VH·(1 − VH/VV)` | Vegetation weighted by depolarization |
| **mRVI** (Modified RVI) | `√(VV/(VV+VH)) · (4·VH/(VV+VH))` | RVI variant, rescaled dynamic range |

Indices that normalize VH against the total power (RVI, DpRVI, CR, PRVI, mRVI)
generally **increase as vegetation grows** because a denser, more randomly
oriented canopy depolarizes the signal and boosts the cross-polarized VH return.
The difference-based measures (PD, NDPI, VV/VH ratio) track the *balance* between
surface and volume scattering, which shifts as a field transitions between bare
soil, emergence, canopy closure, and senescence.

### 3.3 AOI-mean backscatter time series

For the selected index (or raw VV/VH), the module computes the **spatial mean
over the AOI for each acquisition date** (sampled at 10 m) and assembles those
means into a time series. Dates with no valid pixels in the AOI (e.g. fully
masked by border-noise or terrain shadow) are dropped. The result is plotted as
an interactive line chart of *date* versus *AOI-average value*, in dB when the dB
output scale is selected.

### 3.4 Composites and single-date images

Beyond the time series, the corrected, multi-band data can be reduced to single
images for mapping:

- **Single date** — the full multi-band stack (VV, VH, and all nine indices) for
  one acquisition, clipped to the AOI.
- **Composite** — a single index reduced across all (or a filtered subset of)
  dates by a chosen statistic: **mean, median, min, max, amplitude** (max − min),
  **standard deviation, sum,** or **area under the curve (AUC)**. Amplitude and
  standard deviation highlight *how much* a pixel changed over the period;
  AUC is a trapezoidal time-integral of the index, summing
  `Δt·(yᵢ + yᵢ₊₁)/2` between consecutive acquisitions, and approximates
  cumulative seasonal activity.

## 4. Outputs & interpretation

**Backscatter in dB.** Backscatter (σ⁰/γ⁰) expresses how much of the emitted
energy returns to the sensor, in decibels. Higher (less negative) values mean a
stronger echo. As rough guidance over land:

- **Very low (≈ −20 dB or below):** smooth surfaces that reflect energy *away*
  from the sensor — calm open water, smooth roads, dry bare soil. These appear
  dark in radar imagery.
- **Moderate (≈ −15 to −8 dB):** vegetated surfaces and moderately rough ground;
  volume scattering within canopies raises the return.
- **High (≈ −8 dB and above):** strong scatterers — urban structures, dense
  forest with strong double-bounce, or very wet/flooded vegetation, which can
  brighten dramatically.

Because backscatter also rises with **surface moisture** (water has a high
dielectric constant), a sudden brightening across a field can indicate rainfall,
irrigation, or flooding rather than vegetation growth. Interpretation should
always consider moisture alongside structure.

**Polarization channels.**

- **VV** is driven mainly by *surface* scattering and is sensitive to soil
  roughness, soil moisture, and open water. It tends to dominate over bare or
  sparsely vegetated ground.
- **VH** (cross-pol) arises from *volume* scattering inside vegetation; it rises
  as canopies develop and is the more vegetation-responsive channel. A widening
  gap between VV and VH through a season typically tracks canopy growth.

**Index values.** Vegetation-oriented indices (RVI, DpRVI, mRVI, PRVI) trend
**upward through the growing season** as the canopy thickens and depolarizes the
signal, then fall at harvest or senescence — giving a radar analogue of an NDVI
growth curve, but unbroken by cloud. Ratio and difference indices are best read
as indicators of *change in scattering regime* (e.g. bare → vegetated →
harvested) rather than as an absolute biophysical quantity.

**RGB vs single-band rendering.** Exported images can be displayed two ways, and
the choice changes what you see:

- **RGB composite** — three bands (commonly VV, VH, and the VV/VH ratio) are
  mapped to the red, green, and blue channels with a per-band contrast stretch.
  This is a *qualitative* visualization: colour differences reveal land-cover
  contrasts (water, bare soil, vegetation, urban) at a glance, but the colours
  are not values on a scale.
- **Single-band pseudocolor** — one band or index is shown through a
  continuous colour ramp (e.g. Viridis, Magma). This is a *quantitative*
  visualization: each colour corresponds to a specific backscatter or index
  value, so it can be read against a legend and compared between pixels or dates.

## 5. Limitations & caveats

- **Speckle persists.** Even after multi-temporal filtering, SAR retains some
  residual speckle. AOI averaging over many pixels reduces it, but single-pixel
  readings remain noisy — favour area statistics over point sampling.
- **Moisture confounds vegetation signals.** Backscatter responds to both
  canopy structure and surface/soil moisture. A spike may be rain or irrigation,
  not growth. Where possible, corroborate with rainfall records or optical data.
- **Terrain residuals.** Radiometric terrain flattening greatly reduces, but
  does not fully remove, slope effects; steep slopes can still suffer from
  *layover* and *radar shadow* where no usable signal exists. SRTM DEM error
  propagates into the correction.
- **Geometry sensitivity.** Comparisons are only valid within a single orbit
  direction (descending here). Backscatter still varies somewhat with incidence
  angle across the swath.
- **Resolution and mixed pixels.** At ~10 m, small or heterogeneous fields mix
  several cover types within a pixel, blurring the signal.
- **C-band penetration is shallow.** C-band interacts mainly with the upper
  canopy and surface; it saturates over dense forest and cannot probe deep
  biomass the way longer wavelengths (L-band) can.
- **Scale of indices.** Several indices were originally defined for *linear*
  backscatter; applying them to dB-scaled input changes their numeric range and
  meaning. Match the output scale to the index you intend to interpret.

## 6. References

- Mullissa, A., Vollrath, A., Odongo-Braun, C., Slagter, B., Balling, J., Gou,
  Y., Gorelick, N., & Reiche, J. (2021). *Sentinel-1 SAR Backscatter Analysis
  Ready Data Preparation in Google Earth Engine.* Remote Sensing, 13(10), 1954.
  https://doi.org/10.3390/rs13101954
- Vollrath, A., Mullissa, A., & Reiche, J. (2020). *Angular-Based Radiometric
  Slope Correction for Sentinel-1 on Google Earth Engine.* Remote Sensing,
  12(11), 1867. https://doi.org/10.3390/rs12111867
- Lopes, A., Nezry, E., Touzi, R., & Laur, H. (1990). *Maximum A Posteriori
  Speckle Filtering and First-Order Texture Models in SAR Images.* IGARSS '90.
- Quegan, S., & Yu, J. J. (2001). *Filtering of multichannel SAR images.* IEEE
  Transactions on Geoscience and Remote Sensing, 39(11), 2373–2379.
- Lee, J.-S. (1980). *Digital image enhancement and noise filtering by use of
  local statistics.* IEEE Trans. Pattern Analysis and Machine Intelligence,
  PAMI-2(2), 165–168.
- Hird, J. N., DeLancey, E. R., McDermid, G. J., & Kariyeva, J. (2017). *Google
  Earth Engine, Open-Access Satellite Data, and Machine Learning in Support of
  Large-Area Probabilistic Wetland Mapping.* Remote Sensing, 9(12), 1315.
- European Space Agency — Sentinel-1 mission:
  https://sentinel.esa.int/web/sentinel/missions/sentinel-1
