# DEM — Methodology

> EasyDEM delivers ready-to-use terrain elevation data for any area of interest (AOI) on Earth. From a single curated catalogue of roughly thirty public Digital Elevation Models — spanning global radar and optical products to sub-metre national LiDAR surveys — the tool automatically offers only those datasets that actually cover the chosen AOI, clips the selected model to that footprint, and delivers it as a georeferenced elevation raster styled with a perceptually uniform colour ramp. This document describes the data sources, the selection and delivery pipeline, and how to interpret the result.

## 1. Objective

The goal is to make authoritative, analysis-ready elevation data accessible without manual data hunting, tile stitching, or reprojection. A researcher specifies *where* (an AOI) and *which product* (a dataset), and receives a single clean elevation raster covering exactly that area. The tool deliberately stops at the delivery of the **raw elevation surface**: it does not compute slope, hillshade, contours, or any other derived terrain product. Those derivations are intentionally left to the user's GIS so that the choice of method and parameters remains explicit and reproducible.

## 2. Data sources

All elevation models are drawn from public archives hosted on Google Earth Engine (GEE), including the official GEE catalogue and community-curated assets. The catalogue mixes **global** products that cover most of the planet with **regional / national** products that offer much finer detail over a limited area. Resolutions range from **0.5 m** (national LiDAR) to **1800 m** (global relief including ocean floor).

A central distinction runs through the catalogue:

- A **Digital Terrain Model (DTM)** represents the *bare earth* — vegetation and buildings removed. Best for hydrology, geomorphology, and ground-surface analysis.
- A **Digital Surface Model (DSM)** represents the *top of the surface* — including tree canopy and rooftops. Useful for canopy or built-environment studies.

The table below lists the principal datasets. Coverage figures and acquisition periods are as published by each provider.

### Global products

| Dataset | Provider | Native resolution | Coverage | Notes |
|---|---|---|---|---|
| Copernicus GLO-30 | ESA / Copernicus (DLR + Airbus, TanDEM-X) | 30 m | Global | DSM; edited WorldDEM (flattened water, consistent rivers); radar 2011–2015 |
| NASADEM | NASA / USGS | 30 m | 60°N–56°S | Reprocessed SRTM with improved voids/accuracy; radar Feb 2000 |
| SRTM GL1 v003 | NASA / USGS | 30 m (1 arc-sec) | 60°N–56°S | Classic global radar DEM; void-filled v3 |
| ASTER GDEM v3 | NASA / METI (JAXA) | 30 m | 83°N–83°S | Optical stereo (Terra/ASTER) 1999–2011 |
| ALOS AW3D30 v4.1 | JAXA | 30 m | 82°N–82°S | DSM from PRISM optical stereo 2006–2011 |
| MERIT DEM v1.0.3 | University of Tokyo | 90 m | 90°N–60°S | SRTM/AW3D30 with multi-error removal; strong for hydrology |
| CGIAR SRTM v4 | CGIAR-CSI | 90 m | 60°N–56°S | Void-filled 3 arc-sec SRTM |
| GMTED2010 | USGS / NGA | 250 m (7.5 arc-sec) | 84°N–56°S | Successor to GTOPO30; multi-source |
| GTOPO30 | USGS EROS | 1000 m (30 arc-sec) | Global | 1996 legacy DEM; full pole-to-pole reach |
| ETOPO1 | NOAA NGDC | 1800 m (1 arc-min) | Global land + ocean | Relief model including bathymetry (bedrock band) |
| GLOBathy | GLOBathy / sat-io | 30 m | ~1.4 M global lakes | Modelled lake/reservoir maximum depth |

### Regional and national products

| Dataset | Provider | Native resolution | Coverage | Notes |
|---|---|---|---|---|
| Netherlands AHN2 (INT / NON / RUW) | AHN / Rijkswaterstaat | 0.5 m | Netherlands | National airborne LiDAR 2007–2012; interpolated, non-interpolated, and raw-sample variants |
| Netherlands AHN3 | AHN / Rijkswaterstaat | 0.5 m | Netherlands | LiDAR DTM/DSM 2014–2019 |
| Netherlands AHN4 | AHN / Rijkswaterstaat | 0.5 m | Netherlands | LiDAR DTM/DSM 2020–2022 (highest density) |
| USGS 3DEP 1 m | USGS | 1 m | USA (partial) | Highest-resolution US LiDAR DTM |
| NEON DEM | NSF NEON | 1 m | USA (NEON sites) | LiDAR DTM at 81 ecological field sites |
| England 1 m Terrain | Environment Agency (UK) | 1 m | England (~99%) | Composite LiDAR DTM/DSM 2000–2022 |
| France RGE ALTI 1 m | IGN France | 1 m | Metropolitan France | National reference DTM (LiDAR + photogrammetry) 2009–2021 |
| ArcticDEM Mosaic V4.1 / Strips V3 | UMN PGC / NSF | 2 m | Arctic (50–90°N) | Optical stereo; strips retain acquisition dates |
| REMA Strips v1 (2 m) / Mosaic v1.1 (8 m) / Strips v1 (8 m) | UMN PGC / NSF | 2–8 m | Antarctica (S of 60°S) | Reference Elevation Model of Antarctica |
| Australia 5 m DEM | Geoscience Australia | 5 m | Australia | LiDAR + photogrammetry |
| Australia DEM-S / DEM-H | Geoscience Australia | 30 m | Australia | Smoothed, and hydrologically enforced, 1 arc-sec |
| USGS 3DEP 10 m | USGS | 10 m | USA (CONUS + AK + HI) | National standard DEM (supersedes NED) |
| Canada CDEM | Natural Resources Canada | ~23 m | Canada | Multi-resolution national mosaic 1945–2011 |
| Greenland GIMP DEM | Ohio State Univ. / NASA | 30 m | Greenland | Ice-sheet DEM from ASTER/SPOT-5 |
| CryoSat-2 Antarctica DEM | ESA CryoSat-2 / CPOM | 1000 m | Antarctica | Radar altimetry 2010–2016 |

**Vertical datum.** Most global products (SRTM, NASADEM, Copernicus, ALOS, ASTER) reference the EGM96 geoid; some national products use their own official vertical reference (e.g. NAVD88 for US 3DEP, NAP for the Netherlands AHN). Where exact orthometric height matters, consult the linked provider documentation for the dataset chosen.

**Selection guidance.** For most land-surface work the 30 m global products (Copernicus GLO-30, NASADEM, SRTM) are the practical default — complete, consistent, and well documented. Choose a national LiDAR product (AHN, 3DEP, England, France, Australia) when it covers the AOI and fine detail is needed; choose the polar models (ArcticDEM, REMA, GIMP) for ice and high-latitude terrain; and choose MERIT or the Australian DEM-H when hydrological consistency (correct downhill flow) is the priority.

## 3. Methodology

The pipeline runs in three stages: **coverage filtering**, **clipping and export**, and **rendering**.

### 3.1 Dataset selection by AOI

The AOI is defined either by an existing polygon layer or by drawing a box directly on the map. Its outline is dissolved into a single shape and expressed in geographic coordinates (longitude/latitude, EPSG:4326), together with its bounding box.

Once an AOI is set, the catalogue is filtered so that **only datasets that actually overlap the AOI are offered**. This uses a two-stage test designed to be both fast and reliable:

1. **Static bounding-box screen (instant).** Each regional dataset declares the geographic rectangle it covers. If that rectangle does not intersect the AOI bounding box, the dataset is discarded immediately — no network call. This rules out, for example, the Netherlands LiDAR products over a Brazilian AOI in microseconds.
2. **Live presence check (authoritative).** Surviving datasets are queried directly on Earth Engine to confirm that real elevation pixels exist within the AOI (not merely that the AOI falls inside the advertised box). Mosaic-type products are tested for any intersecting tile; single-image products are tested with a coarse pixel count over the AOI. A dataset that returns no data is dropped.

The result is a short, trustworthy list: every dataset offered is known to contain data for the exact area requested. (When the user is not signed in to Earth Engine, this live check is skipped and the full catalogue is shown for browsing.)

### 3.2 Clipping, buffer, and export

Before export the AOI can optionally be **buffered** by −300 m to +300 m. A positive buffer pulls in surrounding terrain (useful for edge context or downstream neighbourhood operations); a negative buffer trims the margins. The buffered region is reduced to a rectangle for the export footprint.

The selected elevation model is then **masked to the AOI** so that pixels outside the polygon become transparent no-data rather than a filled rectangle, and exported as a **GeoTIFF**:

- **Export resolution: a fixed 30 m grid.** Every product is delivered at 30 m regardless of its native resolution. This is the most important consequence of the pipeline for interpretation: sub-30 m sources (AHN at 0.5 m, 3DEP at 1 m, ArcticDEM at 2 m) are **resampled down to 30 m on export**, so their delivered detail matches a 30 m product even though the source is far finer. Sources coarser than 30 m (MERIT, GMTED2010, GTOPO30, ETOPO1) keep their native grid — resampling does not invent detail that the source lacks.
- **Coordinate reference.** The export region is defined in geographic coordinates (EPSG:4326); the GeoTIFF carries full georeferencing and loads directly into any GIS.
- **Values.** Elevation is exported as floating-point metres.

### 3.3 Rendering

The downloaded raster is loaded and displayed as a **single-band pseudocolour layer using the Magma ramp**. The minimum and maximum elevation present in the AOI are read from the raster, and the Magma colour ramp is stretched as a smooth 256-stop interpolation between them. Magma is a *perceptually uniform* sequential ramp: equal steps in elevation correspond to equal perceived steps in colour, so the rendering does not introduce false visual "edges" or hide real gradients — a property that the older rainbow ramps lack.

## 4. Outputs & interpretation

The output is a single GeoTIFF elevation raster plus its on-screen styling.

- **Units.** Pixel values are **elevation in metres** above the dataset's vertical reference (typically the geoid for global products). For ETOPO1 and similar relief models, negative values are below sea level (ocean floor / bathymetry).
- **Colour meaning.** The Magma ramp runs from dark (lowest elevation in the AOI) through purple and red to bright yellow (highest elevation). Because the ramp is stretched to the *local* min/max of the AOI, colours are **relative to the area shown**, not absolute across the globe — the same yellow means "the highest point here," which differs between a floodplain and a mountain AOI. Read the layer's value range to anchor the colours to real heights.
- **Use cases.** Topographic context, visual relief, watershed and catchment analysis, flood and drainage studies (favouring the hydrologically conditioned products), ice-sheet and coastal monitoring at high latitudes, and as the input surface for any slope, aspect, hillshade, or contour analysis the user wishes to run in their GIS.

## 5. Limitations & caveats

- **No derived products.** The tool delivers the elevation surface only. It does **not** compute slope, aspect, hillshade, contours, roughness, or flow direction. These must be generated by the user in their GIS from the delivered raster.
- **Fixed 30 m export ceiling.** All outputs are 30 m. Selecting a 0.5 m or 1 m LiDAR product does **not** yield 0.5 m or 1 m output — it is resampled to 30 m. The fine national models are therefore valuable here mainly for their accuracy and bare-earth quality, not for delivered spatial detail.
- **Source resolution and accuracy vary widely.** A 1800 m global relief model and a 0.5 m LiDAR survey are not interchangeable. Vertical accuracy depends entirely on the source: radar DEMs (SRTM/NASADEM/Copernicus) typically achieve a few metres of vertical error; LiDAR products are far more accurate; coarse legacy models (GTOPO30) much less so.
- **DSM vs DTM.** Surface models (Copernicus GLO-30, ALOS AW3D30, the AHN/England DSM variants) include vegetation and buildings and will read *higher* than the true ground in forested or built areas. Use a DTM product where bare-earth elevation is required.
- **Voids and artefacts.** Original radar and optical DEMs contain data voids (steep terrain, water, radar shadow). Many catalogue products are explicitly void-filled (NASADEM, CGIAR SRTM v4, MERIT, AHN INT); others retain voids by design (AHN NON/RUW). Filled voids are interpolated estimates, not measurements.
- **Vertical datums differ.** Heights from different products are not directly comparable unless reduced to a common vertical reference. Mixing a geoid-referenced global DEM with a nationally-referenced LiDAR DTM can introduce systematic offsets.
- **Acquisition dates differ.** Source data spans 1996 (GTOPO30) to the early 2020s (AHN4). Terrain that has changed since acquisition — quarries, construction, coastal erosion, glacier retreat — will not be reflected in older products.

## 6. References

Each catalogue entry links to its authoritative source documentation. Key references:

- Copernicus DEM GLO-30 — ESA / Copernicus (TanDEM-X, DLR + Airbus). GEE: `COPERNICUS/DEM/GLO30`.
- NASADEM — NASA / USGS. GEE: `NASA/NASADEM_HGT/001`.
- SRTM GL1 v003 — NASA / USGS. GEE: `USGS/SRTMGL1_003`.
- ASTER GDEM v3 — NASA / METI (JAXA). Awesome GEE Community Catalog.
- ALOS World 3D-30 m v4.1 — JAXA. GEE: `JAXA/ALOS/AW3D30/V4_1`.
- MERIT DEM v1.0.3 — University of Tokyo. GEE: `MERIT/DEM/v1_0_3`.
- USGS 3DEP (1 m / 10 m) — USGS 3D Elevation Program.
- Netherlands AHN2/3/4 — AHN / Rijkswaterstaat.
- England 1 m Terrain — Environment Agency (UK); France RGE ALTI — IGN.
- ArcticDEM / REMA — Polar Geospatial Center, University of Minnesota / NSF.
- Australia DEMs — Geoscience Australia; CDEM — Natural Resources Canada.
- GMTED2010 — USGS / NGA; GTOPO30 — USGS EROS; ETOPO1 — NOAA NGDC.

*Elevation data is sourced and processed through Google Earth Engine. Refer to each provider's licence and citation requirements when publishing results.*
