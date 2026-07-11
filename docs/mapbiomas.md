# MapBiomas — Methodology

> This document describes the data and scientific method behind the MapBiomas
> module. The module draws on the MapBiomas Brasil Collection 10 land-use and
> land-cover archive (1985–2024, 30 m resolution) to (1) display the annual
> land-cover classification for an area of interest, (2) detect and date the
> first year each location changed from one land-cover class to another, and
> (3) quantify the converted area, in hectares, per year. The goal is to let a
> researcher see *what* the land was, *what* it became, and *when* the change
> happened, over four decades, for any chosen area in Brazil.

## 1. Objective

The module answers three linked questions about a user-defined area of interest
(AOI):

1. **Coverage** — What was the land cover (forest, pasture, cropland, water,
   urban, etc.) in each year from 1985 to 2024?
2. **Transition** — For a chosen "before → after" change (for example
   pasture becoming cropland, or forest being cleared), in which year did each
   location first make that change?
3. **Area** — How much land (in hectares) underwent that change, broken down
   year by year?

Together these support land-use change analysis, deforestation and regrowth
monitoring, and agricultural-expansion studies at farm to regional scale.

## 2. Data source

All results are derived from **MapBiomas Brasil, Collection 10**, the annual
land-use and land-cover mapping produced by the MapBiomas initiative for the
entire Brazilian territory.

- **Geographic coverage** — Brazil only. The AOI must fall within Brazil for
  the data to be valid.
- **Spatial resolution** — 30 m per pixel, derived primarily from the Landsat
  satellite series. Each 30 m × 30 m pixel therefore represents
  **0.09 hectares** of ground (30 × 30 ÷ 10 000), a constant used throughout the
  area calculations below.
- **Temporal span** — 40 annual maps, one per year from **1985 through 2024**.
- **Class scheme** — Every pixel, in every year, is assigned a single
  land-cover class from the official MapBiomas Collection 10 legend (forest
  formation, savanna, pasture, agriculture, mosaic of uses, urban area, water,
  and so on; Collection 10 adds class 75, photovoltaic plants). The module uses the published MapBiomas class identifiers,
  Portuguese class names, and official color palette unchanged, so that maps and
  legends match the MapBiomas reference exactly.

The underlying product is the Collection 10 **integration asset**: a single,
harmonized annual classification in which each year's map has already been
reconciled across MapBiomas thematic teams into one consistent class per pixel.

## 3. Land-cover coverage

The coverage view shows the annual classification: a map of the AOI for a chosen
year in which every pixel is painted with the color of its land-cover class for
that year. Moving through the years (via a year selector) shows how the
landscape's land cover evolved across the 1985–2024 series.

Each annual map is a *snapshot*, not a measurement of change — it states what
the dominant land cover was at each location in that single year. The class
legend, with its official colors, accompanies the map so each color can be read
back to a named land-cover class. Comparing two years visually already reveals
broad change; the transition analysis (Section 4) makes that change explicit and
datable.

## 4. Transition analysis

A *transition* is the change of a pixel from a chosen set of **source** classes
(the "before" state) to a chosen set of **target** classes (the "after" state) —
for example *pasture → cropland*, *forest → any non-forest* (deforestation), or
*non-forest → forest* (regrowth). The module offers ready-made presets
(pasture-to-crop, deforestation, forest regrowth, agricultural expansion, urban
expansion) and also lets the user define an arbitrary source and target set.

### First-transition-year method

For each location, the method records the **earliest** year in which the
transition occurred, so that a pixel that changed and possibly changed again is
attributed to its first qualifying change. Conceptually, for every year *Y* from
**1986 to 2024** (1986 is the first year that has a prior year, 1985, to compare
against):

1. **Was it source before?** Check whether the pixel belonged to a *source*
   class in the previous year, *Y − 1*.
2. **Did it become target now?** Check whether the same pixel belongs to a
   *target* class in the current year, *Y*.
3. **Flag the change.** If *both* are true — it was a source class in *Y − 1*
   **and** became a target class in *Y* — the pixel is marked as having
   transitioned in year *Y*.
4. **Keep the earliest.** A pixel may satisfy this condition in more than one
   year. The method keeps only the **smallest (earliest) year** for which the
   condition held. Pixels that never made the transition are left blank
   (unmapped).

The result is a single map in which each transitioned pixel carries one number:
the year it first changed from source to target. Pixels that never made the
change carry no value.

### Converted-area statistics

To quantify the change, the method counts how many pixels carry each transition
year (a frequency tabulation of the first-transition-year map). Because every
pixel is a fixed 30 m × 30 m, the area is obtained by multiplying:

> **hectares = number of transitioned pixels × 0.09 ha**

This yields, for each year, the area that first transitioned in that year, plus a
grand total across all years. For very large areas of interest the count is
computed at a slightly coarsened resolution so the calculation remains tractable;
farm- to property-sized areas are unaffected and use the full 30 m detail.

## 5. Outputs & interpretation

The module produces three complementary outputs:

- **Coverage map** — the annual land-cover classification for a selected year,
  colored with the official MapBiomas palette. Read it as *"this is what the
  land was in this year."* Step through years to watch the landscape change.

- **Transition map** — the first-transition-year map, colored by year on a
  diverging (blue → red) scale spanning 1986–2024. Read it as *"this is where
  the change happened, and the color tells you when"* — cooler colors mark early
  transitions, warmer colors mark recent ones. Unchanged land is blank, so the
  colored pixels are exactly the area that made the selected source → target
  change. Because the color scale is pinned to the full 1986–2024 range, a given
  year always has the same color, making maps comparable.

- **Per-year area chart** — a bar chart of converted hectares per transition
  year, with the total for the selected window. Read it as *"how much changed,
  and in which years the change concentrated."* Tall bars mark years of rapid
  conversion.

- **Year-range filter** — a control that narrows the analysis to a sub-window of
  transition years. Both the chart and the transition map respond to it: bars and
  pixels outside the chosen window are de-emphasized, and the reported total
  reflects only the selected years. This isolates, for example, conversion
  during a specific policy period or drought year.

Coverage maps, the transition map, and the per-year chart are meant to be read
together: the coverage maps show the states, the transition map and chart show
the timing and magnitude of the change between those states.

## 6. Limitations & caveats

- **Brazil only.** Collection 10 covers the Brazilian territory exclusively.
  Areas outside Brazil have no data and must not be analyzed with this module.
- **Classification accuracy.** The land-cover classes are themselves a model
  output and carry mapping error. Accuracy varies by class, region, and year;
  rarer and spectrally similar classes (e.g. distinguishing pasture from certain
  croplands or natural grasslands) are harder and more error-prone. Reported
  transitions inherit any misclassification in the two years being compared, so
  isolated single-year flips should be treated with caution.
- **30 m resolution and minimum mapping unit.** Each pixel is 30 m on a side
  (0.09 ha). Features smaller than a pixel, and changes affecting only a few
  pixels, may not be reliably detected; a practical minimum mapping unit applies.
  Hectare totals are estimates built from whole-pixel counts.
- **Annual, calendar-based snapshots.** Each year is a single classification.
  Within-year or sub-annual dynamics (seasonal flooding, crop rotation,
  short-lived clearing) are not represented, and the transition year reflects the
  first year the new class was *mapped*, which can lag the actual change on the
  ground.

## 7. References

- **MapBiomas Project** — Annual land-use and land-cover mapping of Brazil.
  Project, methodology, and data: https://mapbiomas.org
- **Collection 10** — MapBiomas Brasil, Collection 10 of the annual series of
  land-use and land-cover maps of Brazil (1985–2024), integration product.
  See https://brasil.mapbiomas.org for the collection description, accuracy
  assessment, legend, and the official citation to use when publishing results
  derived from this data.
