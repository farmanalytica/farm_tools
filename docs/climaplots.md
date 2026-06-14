# ClimaPlots — Methodology

> ClimaPlots turns decades of daily climate observations for a single point on the
> Earth's surface into a compact climate diagnosis: long-term trends in temperature,
> rainfall and water demand; the average seasonal regime of a place; a panel of
> internationally standardized climate-extreme indices; and a drought index. This
> note describes where the data come from, how each number is derived, and how to
> read the resulting charts. It is written for agronomists, researchers and other
> end users — not for software developers.

## 1. Objective

Given any location (a point you click on the map or a longitude/latitude you type)
and a range of years, ClimaPlots produces a *climate characterization* of that
point built entirely from daily gridded climate data. The deliverables are:

- **Annual trend analysis** — is temperature, rainfall, evapotranspiration, etc.
  rising or falling over the chosen period, and is the change statistically
  meaningful?
- **A thermo-pluviometric (Walter–Lieth style) diagram** — the average monthly
  rainfall and temperature regime, the classic way to summarize a climate and
  identify wet/dry seasons.
- **ETCCDI climate-extreme indices** — a standardized panel of frost days, hot
  days, heavy-rain days, dry/wet spells, etc., the same indicators used in
  climate-change monitoring worldwide.
- **A Standardized Precipitation Index (SPI)** — a drought/wet-spell index that
  expresses rainfall as a statistical anomaly.

This matters because it lets a user assess the climatic suitability and recent
climatic *change* of a farm, watershed, trial site or region without needing GIS
expertise, programming, or a climate-data subscription — all from freely
available, globally consistent datasets.

## 2. Data sources

Two interchangeable daily climate datasets feed the same analysis pipeline. You
can choose either one, and you can overlay a second point (point B) that may use
the *other* source, so the very same location can be compared across both
datasets.

| Dataset | Provider | Variables (native) | Spatial resolution | Temporal resolution | Coverage |
|---|---|---|---|---|---|
| **POWER** | NASA Langley Research Center | T2M_MAX, T2M_MIN, PRECTOTCORR, RH2M, ALLSKY_SFC_SW_DWN, WS2M | ~0.5° × 0.625° grid | Daily | Global, **1981 → present** |
| **ERA5 / ERA5-Land reanalysis** | Open-Meteo (serving ECMWF ERA5) | temperature_2m max/min, precipitation_sum, relative_humidity_2m, shortwave_radiation_sum, wind_speed_10m, et0_fao_evapotranspiration | ~0.25° (ERA5) / ~0.1° (ERA5-Land) | Daily | Global, **1940 → present** |

**NASA POWER** (Prediction Of Worldwide Energy Resources) is a long-running NASA
product tailored for renewable-energy and agroclimatology applications. It
provides bias-corrected satellite- and model-derived daily surface meteorology
on a global grid back to 1981.

**ERA5** is the fifth-generation atmospheric *reanalysis* from the European Centre
for Medium-Range Weather Forecasts (ECMWF). A reanalysis blends a numerical
weather model with all available historical observations to produce a physically
consistent, gap-free record; ERA5 extends back to 1940. ClimaPlots accesses it
through Open-Meteo's free historical archive API.

Both sources are *gridded* products: the value returned for your coordinate is the
estimate for the model/satellite grid cell containing that point, not a physical
weather-station measurement. The two datasets are harmonized to a single set of
variables and units before any analysis:

- **Max / Min Temperature** — °C
- **Precipitation** — mm/day
- **Relative Humidity** — %
- **Irradiation** (surface shortwave) — kWh/m²/day (Open-Meteo's MJ/m²/day is
  divided by 3.6 to match POWER's units)
- **Wind Speed** — m/s (POWER at 2 m, Open-Meteo at 10 m)
- **Reference ET0** and **Growing Degree Days** — derived (see §3)

The default analysis window ends at the **last complete calendar year** (the
previous year) to avoid a partial final year; the start year is clamped to the
earliest year the chosen dataset supports (1981 for POWER, 1940 for ERA5).

## 3. Methodology

### 3.1 Pipeline overview

For each requested point and year range the workflow is:

1. **Retrieve** the daily series from the selected dataset and harmonize it to the
   common variables and units above; provider fill values (e.g. POWER's `-999`)
   are treated as missing data.
2. **Derive** two agronomic variables that are not supplied directly — reference
   evapotranspiration (ET0) and growing degree days (GDD).
3. **Aggregate** the daily series to annual values for trend analysis and to
   long-term monthly means for the climate diagram.
4. **Compute** the ETCCDI extreme indices and the SPI from the daily series.
5. **Test** each annual series for a monotonic trend (Mann–Kendall) and a single
   abrupt change point (Pettitt).
6. **Visualize** the results as the four chart families described in §4.

### 3.2 Derived variables

**Growing Degree Days (GDD).** A measure of accumulated heat available for crop
development above a base temperature (here 10 °C). For each day:

```
Tmean = (Tmax + Tmin) / 2
GDD   = max(Tmean − 10, 0)        (°C·day)
```

Days cooler than the base contribute zero. Summed over a season, GDD tracks the
thermal time a crop has experienced.

**Reference evapotranspiration (ET0).** The atmospheric water demand over a
standard reference surface — the benchmark for irrigation scheduling and water
balance. ClimaPlots uses the **Hargreaves** temperature-based equation, which
needs only Tmax, Tmin and the day's extraterrestrial radiation:

```
ET0 = 0.0023 · (Tmean + 17.8) · √(Tmax − Tmin) · Ra        (mm/day)
```

where `Ra` is the **extraterrestrial radiation** (top-of-atmosphere solar
radiation) for that latitude and day of year, computed with the standard FAO-56
astronomical formulation and converted from MJ/m²/day to mm/day (× 0.408):

```
dr   = 1 + 0.033 · cos(2π·J / 365)                 (inverse Earth–Sun distance)
δ    = 0.409 · sin(2π·J / 365 − 1.39)              (solar declination)
ωs   = arccos(−tan φ · tan δ)                      (sunset hour angle)
Ra   = (24·60/π) · Gsc · dr · [ωs·sin φ·sin δ + cos φ·cos δ·sin ωs]
```

with `J` the day of year, `φ` the latitude in radians, and `Gsc = 0.0820`
MJ·m⁻²·min⁻¹ the solar constant. The Hargreaves method is used for POWER; for
Open-Meteo the ET0 is taken directly from the API's FAO-56 Penman–Monteith
product (a more data-intensive formulation), so the two sources differ slightly in
how ET0 is obtained.

### 3.3 Annual aggregation

For the trend charts the daily data are collapsed to one value per year:

- **Totals** (annual sums) for *Precipitation*, *Reference ET0* and *Growing
  Degree Days* — these are flux/accumulation quantities.
- **Means** (annual averages) for everything else (temperatures, humidity,
  irradiation, wind).

### 3.4 Trend and homogeneity testing

Each annual series is examined with two non-parametric tests at a significance
level of α = 0.05.

- **Mann–Kendall trend test.** A rank-based test that detects whether a series has
  a *monotonic* increasing or decreasing tendency, without assuming any particular
  distribution or a linear shape. It reports the trend direction ("increasing",
  "decreasing" or "no trend") and a p-value; a p-value below 0.05 indicates the
  trend is statistically significant. Being rank-based, it is robust to outliers
  and to non-normal data — well suited to climate series.

- **Pettitt change-point (homogeneity) test.** A rank-based test for a single
  *abrupt shift* in the mean of the series. It tells you whether the series is
  **homogeneous** (no detected break) or **nonhomogeneous**, and if a break is
  found it reports the **probable change-point year**. This flags discontinuities
  that may be climatic (a regime shift) or artificial (a change in the underlying
  data product).

Both tests are reported in the title above each trend/index chart so the
statistical reading travels with the figure.

### 3.5 ETCCDI climate-extreme indices

ClimaPlots computes a panel of indices defined by the WMO Expert Team on Climate
Change Detection and Indices (ETCCDI) — the internationally agreed set used to
monitor changes in temperature and precipitation extremes. They are calculated
from the daily Tmax, Tmin and precipitation series. The panel includes:

*Temperature, annual counts:*
- **Frost Days** — days with Tmin < 0 °C
- **Tropical Nights** — days with Tmin > 20 °C
- **Icing Days** — days with Tmax < 0 °C
- **Summer Days** — days with Tmax > 25 °C

*Temperature, monthly extremes:*
- **TXx / TXn** — monthly maximum and minimum of daily *maximum* temperature
- **TNx / TNn** — monthly maximum and minimum of daily *minimum* temperature
- **Daily Temperature Range (DTR)** — mean Tmax − Tmin

*Precipitation:*
- **Rx1day / Rx5day** — maximum 1-day and consecutive 5-day precipitation totals
- **R10mm / R20mm** — annual count of days with ≥ 10 mm and ≥ 20 mm rainfall
- **SDII** — Simple Daily Intensity Index (mean rainfall on wet days)
- **CDD / CWD** — maximum length of consecutive dry / wet day spells (per month)

### 3.6 Standardized Precipitation Index (SPI)

The SPI expresses precipitation as how unusual it is relative to the location's
own historical distribution, making wet and dry conditions comparable across
climates. ClimaPlots computes a **90-day SPI**:

1. Form a running 90-day accumulated-precipitation series.
2. Fit a **gamma distribution** to those accumulations (location fixed at zero).
3. Transform each accumulation to its cumulative probability under the fitted
   gamma, then map that probability through the **inverse standard-normal**
   function (the probit) to obtain a standardized anomaly.

The result is in standard-deviation units: 0 is the median, positive values are
wetter than normal, negative values drier. Conventionally |SPI| ≥ 2 indicates
extreme conditions, 1.5–2 severe, 1–1.5 moderate.

## 4. Outputs & interpretation

**Annual trends chart.** A line/marker plot of one chosen variable's annual value
over the selected years. Read the slope for the long-term tendency; read the title
for the Mann–Kendall verdict (direction + p-value) and the Pettitt verdict
(homogeneous, or a probable change-point year). The y-axis label states whether
the value is an annual *total* (precipitation, ET0, GDD) or an annual *mean*
(temperatures, humidity, irradiation, wind). When a comparison point B is added,
both series are drawn together, each annotated with its data source, and each gets
its own pair of statistics — useful for comparing two sites, or the same site
across the POWER and ERA5 datasets.

**Thermo-pluviometric diagram.** The location's average yearly climate cycle:
twelve bars of mean monthly rainfall (mm) on the primary axis, with mean monthly
maximum and minimum temperature (°C) as lines on a secondary axis. It is built by
averaging each calendar month across all years in the window. Read it to identify
the rainy and dry seasons, the warmest and coolest months, and — where the
temperature line rises above the rainfall bars — periods of likely water deficit.

**Climate-indices chart.** A time series of any one selected ETCCDI index (units
depend on the index: days, °C, or mm), titled with the same Mann–Kendall and
Pettitt statistics. Rising frost/icing-day counts, falling summer-day counts,
increasing Rx1day, lengthening CDD, etc., are the standard fingerprints of a
changing climate at the site.

**SPI chart.** The 90-day SPI time series in standard-deviation units. Sustained
negative excursions mark droughts; sustained positive excursions mark wet periods.
Because it is normalized to the location's own history, an SPI of −2 means the same
relative severity anywhere.

All series and tables (the raw daily data, annual trends, monthly normals and every
computed index) can be exported for further analysis.

## 5. Limitations & caveats

- **Gridded, not station data.** Every value is the estimate for a model/satellite
  grid cell, not a point measurement. In areas of strong topographic or coastal
  gradients the grid value can differ noticeably from local conditions, and sharp
  microclimate features are smoothed out.
- **Source differences.** POWER and ERA5 are produced by different methods and at
  different resolutions, and they begin in different years (1981 vs. 1940). The
  same location can yield somewhat different absolute values and even different
  trends between the two — comparing them (via point B) is informative, not a
  defect. ET0 is also derived differently (Hargreaves for POWER, FAO-56
  Penman–Monteith for Open-Meteo).
- **Hargreaves ET0** is a temperature-based approximation; it is convenient where
  humidity, wind and radiation are uncertain but is generally less accurate than
  the full Penman–Monteith equation, and can be biased in very humid or very windy
  climates.
- **Statistical assumptions.** Mann–Kendall assumes independent observations;
  strong year-to-year autocorrelation can inflate apparent significance. The
  Pettitt test detects at most one change point and may attribute a *product*
  discontinuity (e.g. a change in satellite inputs) to climate. A "significant"
  trend over a short window may reflect natural multi-year variability rather than
  long-term change — longer records are more reliable.
- **SPI fitting.** The gamma fit is most stable over long records and can be
  sensitive in very arid regimes with many zero-rainfall periods.
- **Trends depend on the chosen window.** Start and end years materially affect
  trend results; choose the longest defensible period and be cautious interpreting
  short ranges.

## 6. References

- Stackhouse, P. W., et al. *NASA Prediction Of Worldwide Energy Resources (POWER)*.
  NASA Langley Research Center. https://power.larc.nasa.gov/
- Hersbach, H., et al. (2020). *The ERA5 global reanalysis.* Quarterly Journal of
  the Royal Meteorological Society, 146(730), 1999–2049. ECMWF.
- Open-Meteo Historical Weather API. https://open-meteo.com/
- Allen, R. G., Pereira, L. S., Raes, D., & Smith, M. (1998). *Crop
  evapotranspiration — Guidelines for computing crop water requirements.* FAO
  Irrigation and Drainage Paper 56, Rome. (ET0, extraterrestrial radiation Ra.)
- Hargreaves, G. H., & Samani, Z. A. (1985). *Reference crop evapotranspiration
  from temperature.* Applied Engineering in Agriculture, 1(2), 96–99.
- Zhang, X., et al. (2011). *Indices for monitoring changes in extremes based on
  daily temperature and precipitation data.* WIREs Climate Change, 2(6), 851–870.
  (ETCCDI indices.)
- McKee, T. B., Doesken, N. J., & Kleist, J. (1993). *The relationship of drought
  frequency and duration to time scales.* Proceedings of the 8th Conference on
  Applied Climatology, 179–184. (SPI.)
- Mann, H. B. (1945). *Nonparametric tests against trend.* Econometrica, 13,
  245–259; Kendall, M. G. (1975). *Rank Correlation Methods.* (Mann–Kendall test.)
- Pettitt, A. N. (1979). *A non-parametric approach to the change-point problem.*
  Journal of the Royal Statistical Society, Series C, 28(2), 126–135.
