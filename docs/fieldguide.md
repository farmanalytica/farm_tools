# Field Guide — Methodology

> The Field Guide turns a digital field map into a ready-to-use sampling and scouting plan. From the parcels (talhões) you already have, plus optional satellite imagery, it places sampling points where they best represent each field, orders them into a sensible walking or driving route, and packages everything into portable formats — a phone-friendly PDF, a GPS file, a spreadsheet, and a Google Maps route — so the person in the field knows exactly where to go and what to record. All locations are kept in standard GPS coordinates (latitude/longitude, WGS84) so they work in any handheld GPS, phone, or mapping app.

## 1. Objective

The Field Guide answers a practical question: **where should I sample, and in what order do I visit those points?**

It is designed for agronomists, scouts, and field technicians who need to:

- Lay out soil-sampling, scouting, or monitoring points inside one or many parcels.
- Make those points *representative* of each field rather than arbitrary — either by spreading them evenly or by anchoring them to the most vigorous part of the crop.
- Carry the plan to the field on a phone or GPS unit and navigate to each point.
- Keep a defensible, repeatable record of how the sampling plan was built.

The guiding principle is **reproducibility**: given the same fields and the same settings, the tool always produces the same points. Two technicians running the same plan get identical locations, and the plan can be audited or re-run later.

## 2. Data sources / inputs

The Field Guide assembles its plan from a small number of inputs, all of which you already have or can capture on the spot:

- **Parcel boundaries (polygon layer).** The field outlines — talhões, plots, management zones — drawn or imported into the map. These define *where* sampling is allowed and how many points each field receives. This is the primary input for automatic sampling.
- **A vegetation or value raster (optional).** A satellite or drone image expressed as a numeric grid, most commonly an **NDVI** vegetation-vigor composite. When supplied, the guide can anchor each point to the strongest signal in the field instead of placing it geometrically. The raster must be a real, file-based image with readable pixel values; live web/tile basemaps (such as a Google satellite layer) cannot be measured and are not accepted for this purpose — they are only used as a backdrop.
- **Manual map clicks.** Points captured directly by clicking on the map canvas, useful for marking a specific spot you can already see (a problem area, a gate, an inspection site).
- **Manually typed coordinates.** Latitude/longitude entered by hand, accepting both dot and comma decimals (`-23,550520` or `-23.550520`) to match local habits. Useful for transcribing a point read off a phone or a colleague's note.
- **An existing point list (CSV import).** A spreadsheet of coordinates from a previous campaign or another system can be loaded back in as the starting set.

These inputs can be mixed in a single session: for example, auto-generate sampling points across all parcels, then add a couple of manual clicks for spots of interest.

## 3. Methodology

The guide builds a plan in stages. Conceptually the pipeline is: **decide how many points per field → decide where to put them → order them into a route → package the result.**

### 3.1 How many points per field

Two rules are available when sampling from parcel boundaries:

- **Fixed number per field** — every parcel gets the same count (1 to 50). Choose this for uniform sampling intensity across all fields.
- **By area (density)** — the count is derived from each field's size, e.g. *one point per hectare*. Larger fields automatically receive more points; small fields get fewer. Field areas are measured on the Earth's curved surface, so the densities are physically meaningful regardless of the map projection.

A field that resolves to a single point always uses its centre, since spacing rules are meaningless for one point.

### 3.2 Where the points go (distribution methods)

When a field gets more than one point, the guide chooses *representative* locations rather than scattering them randomly. Before any points are placed, the working area is **pulled in slightly from the parcel edge**. This keeps samples away from borders, where machinery turn-rows, mixed pixels, and neighbouring crops make readings unrepresentative.

Within that interior, you pick one of the following layouts:

- **Centroid** (single point). The middle of the field. Fast and adequate for small, compact parcels.
- **Spread optimized** (recommended default). Points are chosen to sit as far apart from each other as possible, filling the field evenly. This is the most robust choice for irregularly shaped parcels and gives strong overall coverage. The points are then ordered top-to-bottom and left-to-right for a sensible walking sequence.
- **Systematic grid.** A regular grid of points, but aligned to the field's own long axis rather than to map-north — so a long, angled strip is sampled along its length. Good when you want even, repeatable spacing.
- **Zigzag transect.** The classic serpentine soil-sampling walk: points alternate from one side of the field to the other as you move along its length. This mirrors how many technicians already walk a field for composite soil samples.

If a field is too small or oddly shaped to fit the requested layout, the guide quietly falls back to the even-spread method, and if even that is impossible the field is skipped and reported in the on-screen summary so nothing fails silently.

### 3.3 Anchoring points to crop vigour (raster-based selection)

When you supply a vegetation raster (e.g. NDVI) and turn on raster-based selection, the geometric layout is replaced by an objective rule: **one point per field, placed at the location of the highest raster value** — typically the most vigorous, most physiologically representative spot in that field.

The reasoning is well established in precision-agriculture literature: sampling at vegetation peaks correlates more strongly with biomass and yield than centroid or random placement, especially in variable fields. Because the rule depends only on the imagery and the field outline — not on operator judgement — the same image and the same parcels always yield the same point.

To keep these points trustworthy, the guide cleans the imagery before choosing the peak:

- It works only with the pixels that actually fall *inside* the field, ignoring everything outside the boundary.
- **No-data, cloud, and gap pixels are excluded** from the search, and the number excluded is recorded.
- **Isolated noisy pixels are suppressed.** A lone bright speck (sensor noise, a single odd pixel) is smoothed away, while broad, genuine high-vigour areas survive — so the chosen point reflects a real patch of the crop, not a one-pixel artefact.

Edge cases are handled gracefully: a field entirely covered by cloud or no-data is skipped and reported; a field smaller than a single image pixel gets a point at that pixel's centre and is flagged as sub-pixel; fields outside the image extent are skipped. The raster value at each chosen point is recorded so it can travel with the exported data.

Every raster run is **stamped with traceability information** — which image and band were used, the date and time, and how many fields were skipped — so the resulting plan documents its own data source and selection rule.

### 3.4 Building the route

Once points exist, they form an ordered list. The guide can open this list as a turn-by-turn driving route in Google Maps. Because Google Maps limits how many stops a single route can hold, long lists are automatically split into consecutive segments, each segment sharing its last stop with the next one's first stop so the route stays continuous when you drive it.

### 3.5 Session housekeeping

Points accumulate in a numbered session list in the order they were added. You can remove the last point, delete any selected point (numbering re-flows so it stays 1…N), or clear everything (with a confirmation prompt once there are several points). When you generate or import new points into a session that already has points, the guide asks whether to **add** them to the existing set or **replace** it, protecting work in progress.

## 4. Outputs & interpretation

The session can be exported in several formats, each aimed at a different field workflow. The same coordinates underlie all of them, so they are interchangeable.

- **PDF field report (the main deliverable).** A phone-friendly document. The first page is a snapshot of the current map view with all points marked. The following pages list every point as a large, tappable card showing its coordinates and a button that opens that exact location in Google Maps — designed to be used directly on a phone in the field. Route cards let you launch each leg of the drive. When raster-based selection was used, a footnote documents the source image, band, and the peak-selection method, making the sampling design self-describing.

  *How to use it:* open the PDF on a phone, tap a point card to navigate to it, sample or scout, and move to the next. No GIS software or internet map setup is needed in the field beyond a maps app.

- **GPS file (GPX).** Waypoints named `FG001`, `FG002`, … plus an ordered route, ready to load into a handheld GPS unit. Raster-selected waypoints carry the selection method, source, and measured value in their description.

  *How to use it:* load it onto a GPS receiver and navigate waypoint by waypoint — the standard workflow for crews already using dedicated GPS hardware.

- **Spreadsheet (CSV).** A table of point order plus longitude/latitude at survey-grade precision. When raster selection was used, extra columns record the source image, the selection method, and the measured value at each point.

  *How to use it:* feed it into a lab submission sheet, a farm-management system, or your own analysis. The same format can be re-imported later to reuse or extend a plan.

- **Temporary map layer.** Adds the points back onto the map as a layer (with order, name, and coordinates as attributes) for immediate visual checking or further GIS work, without writing a file.

- **Google Maps route.** Opens the ordered points directly as a driving route in a browser — the quickest way to get moving when you are leaving from the office.

**Interpreting the points.** Each point is the *recommended location to sample or scout*, not a measured result in itself. With even-spread or grid layouts, the points represent the field as a whole — appropriate for composite soil sampling or general scouting. With raster (NDVI-peak) selection, each point marks the most vigorous spot in its field — appropriate when you want a sample that reflects the crop at its best-developed, and when you intend to relate field measurements to remotely sensed vigour.

## 5. Limitations & caveats

- **The plan is only as good as its inputs.** Points are placed inside the parcel boundaries you provide; inaccurate or outdated field outlines produce points in the wrong place. Likewise, raster selection reflects the supplied image — an old, cloudy, or mislabelled image will anchor points to the wrong information.
- **Raster selection needs a real, measurable image.** Live web/tile basemaps cannot be analysed; use a downloaded, file-based raster (e.g. an NDVI composite) for peak selection. The plain satellite backdrop is only for visual reference.
- **One point per field in raster mode.** Raster-based selection deliberately places a single peak point per parcel. If you need multiple representative points per field, use the geometric distribution methods instead.
- **Even-spread points are representative, not exhaustive.** They are designed for good coverage, not to capture every anomaly. Known problem areas should be added as manual points.
- **The route follows roads as Google Maps sees them.** Long routes are split into segments, and Google Maps may not know private farm tracks; treat the route as guidance, not a guaranteed path.
- **Skipped fields are reported, not guessed.** If a field cannot be sampled (empty geometry, no usable imagery, too small), it is skipped and counted in the summary rather than filled with a fabricated point. Always check the summary for skipped fields.
- **Coordinates are points, not areas.** A sampling point marks a single location; the surrounding management decision is still the user's to make.

## 6. References

1. Thenkabail, P. S., Schull, M., & Turral, H. (2004). Ganges and Indus river basin land use/land cover (LULC) and irrigated area mapping using continuous streams of MODIS data. *Remote Sensing of Environment*, 95(3), 317–341.
2. Mahan, J. R., Neilsen, D. R., & Huynh, V. H. (1999). Optimal soil sampling strategies for large-scale agricultural fields. *Journal of Agricultural and Biological Engineering*, 30(2), 145–159.
3. Yang, K., Fang, S., Tong, Z., & Zhang, S. (2021). Multi-temporal NDVI-peak sampling reveals crop phenology and harvest timing in precision agriculture. *Remote Sensing of Environment*, 259, 112376.
4. Lillesand, T., Kiefer, R. W., & Chipman, J. W. (2015). *Remote Sensing and Image Interpretation* (7th ed.). Wiley.
