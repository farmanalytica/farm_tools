# Farm Tools — Methodology Docs

Methodology notes for each Farm Tools module: data sources, processing
pipeline, output interpretation, limitations, and references. Written for the
end user — no code internals.

## Modules

| Module | Document | Summary |
|---|---|---|
| MapBiomas | [mapbiomas.md](mapbiomas.md) | Brazil land-use/land-cover (Collection 9, 1985–2023, 30 m); annual coverage and first-transition-year source→target analysis. |
| Optical | [optical.md](optical.md) | Sentinel-2 surface reflectance; SCL cloud masking, spectral indices, AOI time series, AUC composites. |
| Multi-Satellite | [landsat.md](landsat.md) | Landsat 7/8/9 + Sentinel-2 + HLS + MODIS; per-sensor selection, HSV pan-sharpened 15 m RGB (Landsat), spectral indices, cloud masking, multi-mission SITS. |
| SAR | [sar.md](sar.md) | Sentinel-1 C-band radar; analysis-ready VV/VH backscatter, dual-pol indices, dB time series. |
| SYSI | [sysi.md](sysi.md) | Synthetic Soil Image; GEOS3 bare-soil pixel selection + temporal median for a vegetation-free soil reflectance image. |
| DEM | [dem.md](dem.md) | Digital elevation models from a multi-dataset catalog; AOI-based dataset selection, clipping, and export. |
| ClimaPlots | [climaplots.md](climaplots.md) | Climate time series (NASA POWER, Open-Meteo/ERA5); derived ET0/GDD, trend tests, ETCCDI indices, SPI. |
| Field Guide | [fieldguide.md](fieldguide.md) | Field sampling plans; point distribution, NDVI-peak anchoring, route building, PDF/GPX/CSV outputs. |

Each document is self-contained and follows the same structure: objective,
data sources, methodology, outputs & interpretation, limitations, references.
