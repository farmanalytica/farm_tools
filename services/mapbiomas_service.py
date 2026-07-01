# -*- coding: utf-8 -*-
"""
MapBiomas service.

Brings the MapBiomas Brasil Collection 10 land-use/land-cover archive into the
plugin as an **in-module visualization** (not QGIS layers), mirroring the FARM
web app's feel:

  • **Coverage** — the annual classification rendered to a PNG thumbnail for each
    year (1985–2024), browsed with a year slider inside the module.
  • **Pasture→Crop transition** — a first-transition-year PNG plus the per-year
    converted-area statistics shown as an in-module bar chart.

The Earth Engine logic (asset id, palette, class labels, transition algorithm)
is ported from the web app's ``group_model_gee.py``. ``ee`` is imported lazily
inside methods so the dialog loads before the extlibs bundle is provisioned.
"""

import os
import tempfile

import requests


# --- MapBiomas constants (ported from the FARM web app) ----------------------

MAPBIOMAS_COLLECTION_ASSET = (
    "projects/mapbiomas-public/assets/brazil/lulc/collection10/"
    "mapbiomas_brazil_collection10_coverage_v2"
)
MAPBIOMAS_FIRST_YEAR = 1985
MAPBIOMAS_LATEST_YEAR = 2024
MAPBIOMAS_VIS_MIN = 0
MAPBIOMAS_VIS_MAX = 75

# Official MapBiomas Collection 10 palette, indexed by class ID (0..75), hex
# without '#'. Colors are the authoritative values from agrigee_lite's
# MapBiomas().classes; class IDs with no MapBiomas class are filled white
# ("ffffff") and never occur in the raster. Class 13 (kept from the legacy
# legend) and 75 (Photovoltaic, new in C10) are included.
MAPBIOMAS_PALETTE = [
    "ffffff", "1f8d49", "ffffff", "1f8d49", "7dc975", "04381d", "007785", "ffffff",
    "ffffff", "7a5900", "d6bc74", "519799", "d6bc74", "d89f5c", "ffefc3", "edde8e",
    "ffffff", "ffffff", "e974ed", "c27ba0", "db7093", "ffefc3", "d4271e", "ffa07a",
    "d4271e", "db4d4f", "2532e4", "ffffff", "ffffff", "ffaa5f", "9c0027", "091077",
    "fc8114", "2532e4", "ffffff", "9065d0", "d082de", "ffffff", "ffffff", "f5b3c8",
    "c71585", "f54ca9", "ffffff", "ffffff", "ffffff", "ffffff", "d68fe2", "9932cc",
    "e6ccff", "02d659", "ad5100", "ffffff", "ffffff", "ffffff", "ffffff", "ffffff",
    "ffffff", "ffffff", "ffffff", "ffffff", "ffffff", "ffffff", "ff69b4", "ffffff",
    "ffffff", "ffffff", "ffffff", "ffffff", "ffffff", "ffffff", "ffffff", "ffffff",
    "ffffff", "ffffff", "ffffff", "c12100",
]
# Portuguese legend labels (kept as data, not translated — they come from the
# MapBiomas Collection 10 legend and must match the published class scheme).
MAPBIOMAS_CLASS_LABELS = {
    1: "Floresta",
    3: "Formação Florestal",
    4: "Formação Savânica",
    5: "Mangue",
    6: "Floresta Alagável",
    49: "Restinga Arbórea",
    10: "Formação Natural não Florestal",
    11: "Campo Alagado e Área Pantanosa",
    12: "Formação Campestre",
    32: "Apicum",
    29: "Afloramento Rochoso",
    50: "Restinga Herbácea",
    13: "Outras Formações não Florestais",
    14: "Agropecuária",
    15: "Pastagem",
    18: "Agricultura",
    19: "Lavoura Temporária",
    39: "Soja",
    20: "Cana",
    40: "Arroz",
    62: "Algodão",
    41: "Outras Lavouras Temporárias",
    36: "Lavoura Perene",
    46: "Café",
    47: "Citrus",
    35: "Dendê",
    48: "Outras Lavouras Perenes",
    9: "Silvicultura",
    21: "Mosaico de Usos",
    22: "Área não Vegetada",
    23: "Praia, Duna e Areal",
    24: "Área Urbanizada",
    30: "Mineração",
    25: "Outras Áreas não Vegetadas",
    26: "Corpo D'água",
    33: "Rio, Lago e Oceano",
    31: "Aquicultura",
    27: "Não observado",
    75: "Usina Fotovoltaica",
}
MAPBIOMAS_PASTURE_CLASS = 15
MAPBIOMAS_CROP_CLASSES = (18, 19, 20, 35, 36, 39, 40, 41, 46, 47, 48, 62)

# Thematic class groups (Collection 10 legend) used to build transition presets.
MAPBIOMAS_FOREST_CLASSES = (1, 3, 4, 5, 6, 49)
MAPBIOMAS_NATURAL_CLASSES = MAPBIOMAS_FOREST_CLASSES + (10, 11, 12, 32, 29, 50, 13)
MAPBIOMAS_AGRICULTURE_CLASSES = (MAPBIOMAS_PASTURE_CLASS,) + MAPBIOMAS_CROP_CLASSES + (14, 21)
MAPBIOMAS_URBAN_CLASSES = (24,)
MAPBIOMAS_ANTHROPIC_CLASSES = (
    MAPBIOMAS_AGRICULTURE_CLASSES + (9, 22, 23, 24, 25, 30)
)

# Transition presets: key -> (label, source classes, target classes).
# "First transition year" = first year a pixel went source -> target.
MAPBIOMAS_TRANSITION_PRESETS = {
    "pasture_to_crop": (
        "Pasture → Crop",
        (MAPBIOMAS_PASTURE_CLASS,),
        MAPBIOMAS_CROP_CLASSES,
    ),
    "deforestation": (
        "Deforestation (Forest → anthropic)",
        MAPBIOMAS_FOREST_CLASSES,
        MAPBIOMAS_ANTHROPIC_CLASSES,
    ),
    "regrowth": (
        "Forest regrowth (anthropic → Forest)",
        MAPBIOMAS_ANTHROPIC_CLASSES,
        MAPBIOMAS_FOREST_CLASSES,
    ),
    "ag_expansion": (
        "Agricultural expansion (natural → pasture/crop)",
        MAPBIOMAS_NATURAL_CLASSES,
        (MAPBIOMAS_PASTURE_CLASS,) + MAPBIOMAS_CROP_CLASSES,
    ),
    "urban_expansion": (
        "Urban expansion (→ Urban)",
        MAPBIOMAS_NATURAL_CLASSES + MAPBIOMAS_AGRICULTURE_CLASSES,
        MAPBIOMAS_URBAN_CLASSES,
    ),
}

MAPBIOMAS_TRANSITION_FIRST_YEAR = 1986
MAPBIOMAS_TRANSITION_LAST_YEAR = 2024
# Diverging blue→red gradient (18 stops) spanning the transition years.
MAPBIOMAS_TRANSITION_PALETTE = [
    "2c7bb6", "3f8fc1", "5ea3cb", "7eb7d4", "9ecbdd", "bedfe6", "deeff0", "ffffbf",
    "fee9a4", "fed489", "fdbe6f", "fda254", "fc8939", "f5701f", "ea5212", "d7301f",
    "b81409", "990000",
]

# 30 m MapBiomas pixel → hectares.
_PIXEL_AREA_HA = 30 * 30 / 10_000

# Thumbnail size (longest edge, px) for the in-module PNG previews.
_THUMB_DIMENSIONS = 1024

# Study-area boundary line drawn on top of every thumbnail. Black reads
# against both the coverage land-cover palette and the transition
# blue->red diverging palette, where a red line would blend into the hot end.
_BOUNDARY_COLOR = "000000"
_BOUNDARY_WIDTH = 2


class MapBiomasService:
    """Service layer for the MapBiomas coverage + transition previews."""

    # ------------------------------------------------------------------
    # Earth Engine image builders
    # ------------------------------------------------------------------

    @staticmethod
    def _region(aoi):
        """GeoJSON bounding box of the AOI, used as the thumbnail region."""
        return aoi.geometry().bounds().getInfo()

    @staticmethod
    def _boundary_overlay(aoi):
        """RGB line image tracing *aoi*'s polygon edge, masked everywhere else.

        Meant to be ``.blend()``-ed on top of an already-clipped, already-
        visualized image so the study-area contour stays visible against the
        classification colors instead of relying on the clip's transparent
        edge alone.
        """
        import ee

        line = ee.Image().byte().paint(aoi, 1, _BOUNDARY_WIDTH)
        return line.selfMask().visualize(palette=[_BOUNDARY_COLOR])

    @staticmethod
    def _coverage_visualized(aoi, year):
        import ee

        geometry = aoi.geometry()
        image = ee.Image(MAPBIOMAS_COLLECTION_ASSET).select(
            f"classification_{year}"
        ).clip(geometry)
        visualized = image.visualize(
            min=MAPBIOMAS_VIS_MIN, max=MAPBIOMAS_VIS_MAX, palette=MAPBIOMAS_PALETTE
        )
        return visualized.blend(MapBiomasService._boundary_overlay(aoi))

    @staticmethod
    def _build_first_transition_year_image(aoi, source_classes, target_classes):
        """Per-pixel earliest *source → target* transition year, clipped to *aoi*.

        A pixel transitions in year Y when it belonged to one of
        *source_classes* in Y-1 and to one of *target_classes* in Y. Returns an
        ``ee.Image`` with band ``first_year``, masked outside any transition.
        """
        import ee

        base = ee.Image(MAPBIOMAS_COLLECTION_ASSET)
        src_list = ee.List(list(source_classes))
        src_ones = ee.List([1] * len(source_classes))
        tgt_list = ee.List(list(target_classes))
        tgt_ones = ee.List([1] * len(target_classes))
        images = []
        for year in range(
            MAPBIOMAS_TRANSITION_FIRST_YEAR, MAPBIOMAS_TRANSITION_LAST_YEAR + 1
        ):
            prev_band = base.select(f"classification_{year - 1}")
            cur_band = base.select(f"classification_{year}")
            was_source = prev_band.remap(src_list, src_ones, 0)
            became_target = cur_band.remap(tgt_list, tgt_ones, 0)
            flipped = was_source.And(became_target)
            images.append(
                flipped.multiply(year).toInt16().selfMask().rename("first_year")
            )
        return ee.ImageCollection(images).min().rename("first_year").clip(aoi.geometry())

    # ------------------------------------------------------------------
    # Thumbnail download
    # ------------------------------------------------------------------

    @staticmethod
    def _download_thumb(visualized, region, output_path, timeout=180):
        url = visualized.getThumbURL({
            "region": region,
            "dimensions": _THUMB_DIMENSIONS,
            "format": "png",
        })
        response = requests.get(url, timeout=timeout)
        if not response.ok:
            raise RuntimeError(
                "MapBiomas thumbnail failed (HTTP {}): {}".format(
                    response.status_code, response.reason
                )
            )
        with open(output_path, "wb") as fh:
            fh.write(response.content)
        return output_path

    @staticmethod
    def download_coverage_thumbnails(
        aoi, output_dir, progress_cb=None, cancel_cb=None
    ):
        """Render every coverage year to a PNG in *output_dir*.

        Returns ``{year: png_path}``. ``progress_cb(message, done, total)`` is
        called as each year completes; ``cancel_cb()`` (if given) stops queuing
        new years when truthy.

        The 39 ``getThumbURL`` round-trips run concurrently — each blocking
        EE-URL-resolve + ``requests.get`` + write is offloaded with
        ``asyncio.to_thread`` and a ``Semaphore`` caps the in-flight count, so
        the whole batch transfers in parallel instead of one year at a time
        (same fan-out as ``LandsatService.download_superres_batch``). The PNG
        output is byte-identical to the previous serial loop.
        """
        import asyncio

        os.makedirs(output_dir, exist_ok=True)
        region = MapBiomasService._region(aoi)
        years = list(range(MAPBIOMAS_FIRST_YEAR, MAPBIOMAS_LATEST_YEAR + 1))
        total = len(years)

        # Cap simultaneous EE round-trips / byte transfers. Mirrors the optical
        # fan-out; well under EE's per-request concurrency ceiling.
        max_parallel = 20

        def _cancelled():
            return cancel_cb is not None and cancel_cb()

        def _download_one(year):
            path = os.path.join(output_dir, f"coverage_{year}.png")
            MapBiomasService._download_thumb(
                MapBiomasService._coverage_visualized(aoi, year), region, path
            )
            return path

        async def _fetch(year, semaphore, counter, images):
            async with semaphore:
                if _cancelled():
                    return
                try:
                    path = await asyncio.wait_for(
                        asyncio.to_thread(_download_one, year), timeout=240
                    )
                    images[year] = path
                except Exception:
                    path = None
                counter["done"] += 1
                if progress_cb:
                    progress_cb(f"MapBiomas {year}", counter["done"], total)

        async def _run():
            semaphore = asyncio.Semaphore(max_parallel)
            counter = {"done": 0}
            images = {}
            await asyncio.gather(*[
                _fetch(year, semaphore, counter, images) for year in years
            ])
            return images

        images = asyncio.run(_run())
        if progress_cb:
            progress_cb("Done", total, total)
        return images

    @staticmethod
    def download_transition(
        aoi, output_dir, source_classes, target_classes, progress_cb=None
    ):
        """Render the transition PNG and compute per-year converted hectares.

        *source_classes* / *target_classes* define the transition (see
        :data:`MAPBIOMAS_TRANSITION_PRESETS`). Returns ``(png_path, stats)``
        where stats is
        ``{"total_hectares": float, "per_year": [{"year", "hectares"}, …]}``.
        """
        import ee

        os.makedirs(output_dir, exist_ok=True)
        region = MapBiomasService._region(aoi)
        first_year = MapBiomasService._build_first_transition_year_image(
            aoi, source_classes, target_classes
        )

        if progress_cb:
            progress_cb("Rendering transition", 0, 2)
        visualized = first_year.visualize(
            min=MAPBIOMAS_TRANSITION_FIRST_YEAR,
            max=MAPBIOMAS_TRANSITION_LAST_YEAR,
            palette=MAPBIOMAS_TRANSITION_PALETTE,
        ).blend(MapBiomasService._boundary_overlay(aoi))
        path = os.path.join(output_dir, "transition.png")
        MapBiomasService._download_thumb(visualized, region, path, timeout=240)

        if progress_cb:
            progress_cb("Computing statistics", 1, 2)
        # agrigee_lite's adaptive pixel cap (absolute count here, so identical to
        # the previous 1e9 for normal AOIs) plus ``bestEffort=True``: an AOI that
        # would exceed the cap is auto-coarsened by EE instead of raising
        # "Too many pixels", so oversized fields still return stats. Farm-sized
        # AOIs stay far under the cap and are unaffected.
        from agrigee_lite.ee_utils import ee_get_number_of_pixels

        histogram = first_year.reduceRegion(
            reducer=ee.Reducer.frequencyHistogram(),
            geometry=aoi.geometry(),
            scale=30,
            maxPixels=ee_get_number_of_pixels(aoi.geometry(), 1e9, 30),
            bestEffort=True,
        ).get("first_year")
        raw_hist = histogram.getInfo() or {}

        per_year = []
        total_ha = 0.0
        for year in range(
            MAPBIOMAS_TRANSITION_FIRST_YEAR, MAPBIOMAS_TRANSITION_LAST_YEAR + 1
        ):
            count = float(raw_hist.get(str(year), 0) or 0)
            hectares = round(count * _PIXEL_AREA_HA, 3)
            total_ha += hectares
            per_year.append({"year": year, "hectares": hectares})

        if progress_cb:
            progress_cb("Done", 2, 2)
        stats = {"total_hectares": round(total_ha, 3), "per_year": per_year}
        return path, stats

    @staticmethod
    def render_transition_map(
        aoi, output_dir, source_classes, target_classes,
        year_min=None, year_max=None, progress_cb=None,
    ):
        """Render only the transition PNG for a year window (no stats).

        Same first-transition-year image as :meth:`download_transition`, but when
        *year_min* / *year_max* narrow the full span the out-of-window pixels are
        masked so the map shows only the selected transition years. The color
        scale stays pinned to the full 1986–2024 range, so a pixel keeps the same
        year color regardless of the window. Returns the PNG path.

        Used to keep the in-module transition map in sync with the year-range
        slider; stats are unchanged (the chart filters client-side), so this
        re-renders the image alone.
        """
        os.makedirs(output_dir, exist_ok=True)
        region = MapBiomasService._region(aoi)
        first_year = MapBiomasService._build_first_transition_year_image(
            aoi, source_classes, target_classes
        )
        if year_min is not None and year_max is not None and (
            year_min > MAPBIOMAS_TRANSITION_FIRST_YEAR
            or year_max < MAPBIOMAS_TRANSITION_LAST_YEAR
        ):
            in_range = first_year.gte(year_min).And(first_year.lte(year_max))
            first_year = first_year.updateMask(in_range)

        if progress_cb:
            progress_cb("Rendering transition map", 0, 1)
        visualized = first_year.visualize(
            min=MAPBIOMAS_TRANSITION_FIRST_YEAR,
            max=MAPBIOMAS_TRANSITION_LAST_YEAR,
            palette=MAPBIOMAS_TRANSITION_PALETTE,
        ).blend(MapBiomasService._boundary_overlay(aoi))
        path = os.path.join(
            output_dir, "transition_{0}_{1}.png".format(year_min, year_max)
        )
        MapBiomasService._download_thumb(visualized, region, path, timeout=240)
        if progress_cb:
            progress_cb("Done", 1, 1)
        return path

    # ------------------------------------------------------------------
    # GeoTIFF download (single year → QGIS layer)
    # ------------------------------------------------------------------

    @staticmethod
    def download_coverage_geotiff(aoi, year, output_folder=None):
        """Download the raw single-band classification GeoTIFF for *year*.

        Unlike the thumbnails, this keeps the MapBiomas class IDs as pixel values
        so the result can be styled with a categorical renderer and queried in
        QGIS. Returns the local file path.
        """
        import ee

        geometry = aoi.geometry()
        image = (
            ee.Image(MAPBIOMAS_COLLECTION_ASSET)
            .select(f"classification_{year}")
            .rename("classification")
            .clip(geometry)
        )
        url = image.getDownloadURL({
            "scale": 30,
            "region": geometry.bounds().getInfo(),
            "format": "GeoTIFF",
            "crs": "EPSG:4326",
        })
        response = requests.get(url, timeout=300)
        if not response.ok:
            raise RuntimeError(
                "MapBiomas download failed (HTTP {}): {}".format(
                    response.status_code, response.reason
                )
            )

        target_dir = (
            output_folder
            if (output_folder and os.path.isdir(output_folder))
            else tempfile.gettempdir()
        )
        output_path = MapBiomasService._get_unique_path(
            target_dir, f"MapBiomas_coverage_{year}.tif"
        )
        with open(output_path, "wb") as fh:
            fh.write(response.content)
        return output_path

    @staticmethod
    def download_transition_geotiff(
        aoi, source_classes, target_classes, output_folder=None,
        year_min=None, year_max=None
    ):
        """Download the raw first-transition-year GeoTIFF (band ``first_year``).

        Pixel values are the transition year (1986–2024), masked elsewhere — so
        the layer can be classed by year in QGIS. When *year_min* / *year_max*
        are given, pixels outside that transition-year window are masked out, so
        the exported layer matches the year range chosen in the plot. Returns
        the local file path.
        """
        first_year = MapBiomasService._build_first_transition_year_image(
            aoi, source_classes, target_classes
        )
        if year_min is not None and year_max is not None and (
            year_min > MAPBIOMAS_TRANSITION_FIRST_YEAR
            or year_max < MAPBIOMAS_TRANSITION_LAST_YEAR
        ):
            in_range = first_year.gte(year_min).And(first_year.lte(year_max))
            first_year = first_year.updateMask(in_range)
        url = first_year.getDownloadURL({
            "scale": 30,
            "region": aoi.geometry().bounds().getInfo(),
            "format": "GeoTIFF",
            "crs": "EPSG:4326",
        })
        response = requests.get(url, timeout=300)
        if not response.ok:
            raise RuntimeError(
                "MapBiomas transition download failed (HTTP {}): {}".format(
                    response.status_code, response.reason
                )
            )
        target_dir = (
            output_folder
            if (output_folder and os.path.isdir(output_folder))
            else tempfile.gettempdir()
        )
        output_path = MapBiomasService._get_unique_path(
            target_dir, "MapBiomas_transition.tif"
        )
        with open(output_path, "wb") as fh:
            fh.write(response.content)
        return output_path

    @staticmethod
    def _get_unique_path(folder, filename):
        candidate = os.path.join(folder, filename)
        if not os.path.exists(candidate):
            return candidate
        basename, ext = os.path.splitext(filename)
        counter = 1
        while True:
            candidate = os.path.join(folder, f"{basename}_{counter}{ext}")
            if not os.path.exists(candidate):
                return candidate
            counter += 1
