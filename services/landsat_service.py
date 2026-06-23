# -*- coding: utf-8 -*-
"""
Landsat service layer (Super-Resolution page).

Wraps ``agrigee_lite`` Landsat 7/8/9 sources to deliver:

* **Super-resolution RGB** — HSV pan-sharpening merges the 15 m panchromatic
  band into RGB, taking Landsat from 30 m to an effective 15 m. The library
  only allows this on Top-of-Atmosphere (TOA) products, so super-res imagery is
  TOA reflectance, not surface reflectance.
* **Vegetation indices** and **multispectral RGB** — computed on the
  atmospherically-corrected Surface Reflectance (SR) product (30 m).

All Earth-Engine / ``agrigee_lite`` specifics live here, off the UI thread
(callers run these from QThread workers). Single-date downloads reuse the
plugin's established ``getDownloadURL`` + ``requests`` pattern (see
``OpticalService``). The batch super-res download runs that same per-scene
pattern concurrently with pure asyncio (``asyncio.to_thread`` + a ``Semaphore``)
so the many scenes transfer in parallel; each scene is still requested as a
single multiband GeoTIFF, so no zip extraction or band merging is required (see
``download_superres_batch``).
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional

import requests

try:
    from osgeo import gdal
except ImportError:
    gdal = None


# Satellite sources are declared in the ``SATELLITES`` registry (defined after
# ``_mission_class`` below, once the build helpers it references exist).
# ``MISSIONS`` — the ordered display-name list the page iterates — is derived
# from it. All agrigee_lite classes are imported lazily inside the build
# closures because the library only lands on sys.path after extlibs
# provisioning.

# Vegetation indices computable from the six Landsat SR bands
# (blue, green, red, nir, swir1, swir2). Display name -> agrigee_lite key.
# Red-edge indices (NDRE, MTCI, …) are intentionally absent: Landsat has no
# red-edge band. Keys must exist in agrigee_lite.vegetation_indices.
LANDSAT_INDEX_KEYS = {
    "NDVI": "ndvi",
    "GNDVI": "gndvi",
    "EVI": "evi",
    "EVI2": "evi2",
    "SAVI": "savi",
    "OSAVI": "osavi",
    "MSAVI": "msavi",
    "ARVI": "arvi",
    "NDWI": "ndwi",
    "MNDWI": "mndwi",
    "BSI": "bsi",
    "CIgreen": "ci_green",
    "CIred": "ci_red",
    "MCARI": "mcari",
}
LANDSAT_INDEX_ORDER = list(LANDSAT_INDEX_KEYS.keys())

# Multispectral RGB render modes over the SR bands. Friendly-band triples are
# resolved to numeral band names at download time. itemData carries the stable
# English key so the renderer survives a translated UI (same trick as optical).
MULTISPECTRAL_MODES = {
    "RGB: Real Color": ("red", "green", "blue"),
    "RGB: NIR-Red-Green": ("nir", "red", "green"),
    "RGB: SWIR1-NIR-Red": ("swir1", "nir", "red"),
    "RGB: SWIR2-NIR-Green": ("swir2", "nir", "green"),
}


def _mission_class(mission: str):
    """Return the agrigee_lite satellite class for a mission display name."""
    from agrigee_lite.sat.landsat import Landsat7, Landsat8, Landsat9

    return {
        "Landsat 7": Landsat7,
        "Landsat 8": Landsat8,
        "Landsat 9": Landsat9,
    }[mission]


# -- per-sensor build closures ---------------------------------------------
# Each returns a configured (but not yet min-valid-tuned) agrigee_lite sat.
# Constructors differ per sensor, so the differences are absorbed here rather
# than leaking into the service methods: Landsat takes ``tier`` +
# ``use_cloud_mask`` (+ optional pan-sharpening), Sentinel-2 a Cloud Score Plus
# threshold, HLS a Fmask quality flag. ``tier`` is accepted by every closure for
# a uniform call site even where the sensor ignores it.
def _landsat_builders(mission: str):
    """Return ``(build_sr, build_superres)`` closures for a Landsat mission."""

    def build_sr(indices, use_cloud_mask, tier):
        return _mission_class(mission)(
            indices=indices, use_sr=True, tier=tier,
            use_cloud_mask=use_cloud_mask, border_pixels_to_erode=0,
        )

    def build_superres(use_cloud_mask, tier):
        # TOA + pan band are mandatory for pan-sharpening or agrigee_lite raises.
        return _mission_class(mission)(
            bands={"blue", "green", "red", "pan"}, use_sr=False,
            use_pan_sharpening=True, tier=tier,
            use_cloud_mask=use_cloud_mask, border_pixels_to_erode=0,
        )

    return build_sr, build_superres


def _s2_build_sr(indices, use_cloud_mask, tier):
    """Sentinel-2 SR (10 m, BOA from 2019). No ``tier``; clouds are handled by
    Cloud Score Plus, so unchecking the mask relaxes its threshold to 0 (keep
    every pixel) rather than toggling a QA bitmask."""
    from agrigee_lite.sat.sentinel2 import Sentinel2

    return Sentinel2(
        indices=indices, use_sr=True,
        cloud_probability_threshold=0.7 if use_cloud_mask else 0.0,
        border_pixels_to_erode=0,
    )


def _hls_s2_build_sr(indices, use_cloud_mask, tier):
    """HLS Sentinel-2 (30 m, harmonised to Landsat). Fmask quality mask in place
    of the QA bitmask; no ``tier``."""
    from agrigee_lite.sat.hls import HLSSentinel2

    return HLSSentinel2(
        indices=indices, use_quality_mask=use_cloud_mask,
        border_pixels_to_erode=0,
    )


def _modis_build_sr(indices, use_cloud_mask, tier):
    """MODIS Terra+Aqua 8-day composites (250 m). Carries only red+nir bands, so
    no RGB composite and only the red/nir vegetation indices (see
    ``_MODIS_INDEX_KEYS``). No ``tier``."""
    from agrigee_lite.sat.modis import Modis8Days

    return Modis8Days(
        indices=indices, use_cloud_mask=use_cloud_mask,
        border_pixels_to_erode=0,
    )


# Indices computable from MODIS's two bands (red, nir) only — agrigee_lite's
# ``availableIndices`` would reject the rest (they need green/blue/swir). Subset
# of LANDSAT_INDEX_KEYS so the keys stay in sync.
_MODIS_INDEX_KEYS = {
    name: LANDSAT_INDEX_KEYS[name]
    for name in ("NDVI", "EVI2", "SAVI", "OSAVI", "MSAVI", "CIred")
}


@dataclass(frozen=True)
class SatSpec:
    """Declarative capabilities of one satellite source on the page.

    ``build_sr`` builds the surface-reflectance sat used for indices, the
    multispectral RGB composite and date discovery. ``build_superres`` builds
    the pan-sharpened TOA sat for the 15 m super-res product; ``None`` means the
    sensor has no panchromatic band and the super-res action is unavailable for
    it. ``index_keys`` is the subset of vegetation indices the sensor's bands can
    compute (display name -> agrigee_lite key); ``color`` is the time-series
    trace colour.
    """

    label: str
    build_sr: Callable                              # (indices, use_cloud_mask, tier) -> sat
    pixel_size: int
    build_superres: Optional[Callable] = None       # (use_cloud_mask, tier) -> sat | None
    multispectral: bool = True
    index_keys: dict = field(default_factory=lambda: dict(LANDSAT_INDEX_KEYS))
    color: str = "#1b6b39"
    default_on: bool = True                          # checkbox state on first show

    @property
    def has_superres(self) -> bool:
        return self.build_superres is not None


def _landsat_spec(label: str, color: str) -> SatSpec:
    build_sr, build_superres = _landsat_builders(label)
    return SatSpec(
        label=label, build_sr=build_sr, build_superres=build_superres,
        pixel_size=30, color=color,
    )


# Registry of selectable sources, in display order. Landsat 5 stays out (no pan
# band → no super-res, the historical headline feature). Sentinel-2 and HLS add
# genuine multi-satellite coverage; both are optical and share the friendly band
# vocabulary, so the RGB modes and indices port unchanged. Neither carries a
# panchromatic band, so ``build_superres`` is None (S-2's native 10 m already
# beats Landsat's pan-sharpened 15 m).
SATELLITES = {
    spec.label: spec
    for spec in (
        _landsat_spec("Landsat 8", "#1b6b39"),
        _landsat_spec("Landsat 9", "#2a5d84"),
        _landsat_spec("Landsat 7", "#d98f00"),
        SatSpec("Sentinel-2", _s2_build_sr, pixel_size=10, color="#7b3fa0"),
        SatSpec("HLS Sentinel-2", _hls_s2_build_sr, pixel_size=30, color="#0a7e8c"),
        # MODIS: 250 m, red+nir only — no RGB composite, reduced index set, and
        # off by default (coarse; opt-in to keep the default run light).
        SatSpec(
            "MODIS (8-day)", _modis_build_sr, pixel_size=250, color="#c2410c",
            multispectral=False, index_keys=_MODIS_INDEX_KEYS, default_on=False,
        ),
    )
}

# Ordered display-name list the page iterates (date discovery, time-series
# merge, batch). Derived from the registry so a new source appears everywhere by
# adding one ``SATELLITES`` entry.
MISSIONS = list(SATELLITES)

# Per-mission trace colours, surfaced for the controller's chart renderer.
MISSION_COLORS = {label: spec.color for label, spec in SATELLITES.items()}


class LandsatService:
    """Earth-Engine logic for the Landsat super-resolution page."""

    # -- satellite builders ------------------------------------------------
    @staticmethod
    def _apply_min_valid(sat, aoi_area_m2, min_valid_pct):
        """Translate a "min valid coverage %" into agrigee_lite's absolute
        ``min_valid_pixel_count`` for this satellite and apply it.

        The count is the requested percentage of the pixels a fully-covered,
        cloud-free image over the AOI would hold at the satellite's native
        resolution (``pct/100 * AOI_area / pixelSize²``). Because super-res
        (15 m) and SR (30 m) sats have different ``pixelSize``, the same
        percentage maps to a different count on each — hence keying off
        ``sat.pixelSize`` rather than a constant.

        Left at the library default when no percentage or AOI area is supplied,
        so callers that pass neither keep the previous behaviour.
        """
        if min_valid_pct and min_valid_pct > 0 and aoi_area_m2 and aoi_area_m2 > 0:
            total_pixels = aoi_area_m2 / float(sat.pixelSize ** 2)
            sat.minValidPixelCount = max(0, int(round(total_pixels * min_valid_pct / 100.0)))
        return sat

    @staticmethod
    def _build_superres_sat(
        mission: str, use_cloud_mask: bool, tier: int,
        min_valid_pct: float = 0, aoi_area_m2: float = None,
    ):
        """TOA + pan-sharpening satellite (effective 15 m) for ``mission``.

        Raises ValueError for sensors without a panchromatic band (Sentinel-2,
        HLS, …) — the page must gate the super-res action on
        ``SATELLITES[mission].has_superres``.
        """
        spec = SATELLITES[mission]
        if not spec.has_superres:
            raise ValueError(
                f"{mission} has no panchromatic band; super-resolution is unavailable."
            )
        sat = spec.build_superres(use_cloud_mask, tier)
        return LandsatService._apply_min_valid(sat, aoi_area_m2, min_valid_pct)

    @staticmethod
    def _build_sr_sat(
        mission: str, use_cloud_mask: bool, tier: int, indices=None,
        min_valid_pct: float = 0, aoi_area_m2: float = None,
    ):
        """Surface-reflectance satellite for ``mission`` (native resolution),
        optionally with indices. Dispatches to the registry build closure, which
        absorbs the per-sensor constructor differences."""
        sat = SATELLITES[mission].build_sr(indices, use_cloud_mask, tier)
        return LandsatService._apply_min_valid(sat, aoi_area_m2, min_valid_pct)

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _feature(aoi: ee.FeatureCollection, date_start: str, date_end: str) -> ee.Feature:
        """agrigee_lite expects a feature carrying ``s``/``e`` date strings and a
        dummy index ``0`` (used by its download/compute code paths)."""
        import ee

        return ee.Feature(aoi.geometry(), {"s": date_start, "e": date_end, "0": 1})

    @staticmethod
    def _single_date_feature(aoi: ee.FeatureCollection, date: str) -> ee.Feature:
        next_date = (
            datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)
        ).strftime("%Y-%m-%d")
        return LandsatService._feature(aoi, date, next_date)

    @staticmethod
    def _numeral_band(sat, friendly: str) -> str:
        """Map a friendly band name (e.g. ``"red"``) to the numeral name
        agrigee_lite renames it to (e.g. ``"13_red"``). Robust to the library's
        ``sorted(bands)`` ordering."""
        for friendly_name, numeral_name in sat.selectedBands:
            if friendly_name == friendly:
                return numeral_name
        raise KeyError(f"Band '{friendly}' not selected on satellite.")

    @staticmethod
    def _numeral_index(sat, index_key: str) -> str:
        for _expr, name, numeral_name in sat.selectedIndices:
            if name == index_key:
                return numeral_name
        raise KeyError(f"Index '{index_key}' not selected on satellite.")

    @staticmethod
    def _region(aoi: ee.FeatureCollection, buffer_m: float):
        geometry = aoi.geometry()
        if buffer_m:
            geometry = geometry.buffer(buffer_m)
        return geometry

    # -- date discovery (Run) ---------------------------------------------
    @staticmethod
    def list_dated_missions(
        aoi: ee.FeatureCollection,
        date_start: str,
        date_end: str,
        use_cloud_mask: bool = True,
        tier: int = 1,
        min_valid_pct: float = 0,
        aoi_area_m2: float = None,
        missions: list = None,
    ) -> list:
        """Available acquisition dates over the AOI/date-range across the
        selected missions (default: every registered satellite), as
        ``(date, mission)`` tuples sorted by date.

        ``ZZ_USER_TIME_DUMMY`` is the per-image date string agrigee_lite tags
        during its valid-pixel filtering step. Missions whose temporal range
        falls outside the request simply return no dates.

        ``min_valid_pct`` (0–100) discards any date whose valid-pixel coverage
        of the AOI falls below it — see ``_apply_min_valid``.
        """
        feature = LandsatService._feature(aoi, date_start, date_end)
        out = []
        for mission in (missions or MISSIONS):
            sat = LandsatService._build_sr_sat(
                mission, use_cloud_mask, tier,
                min_valid_pct=min_valid_pct, aoi_area_m2=aoi_area_m2,
            )
            dates = sat.imageCollection(feature).aggregate_array(
                "ZZ_USER_TIME_DUMMY"
            ).getInfo()
            for date in set(dates or []):
                out.append((date, mission))
        out.sort(key=lambda pair: (pair[0], pair[1]))
        return out

    # -- index time series (agrigee_lite SITS) ----------------------------
    @staticmethod
    def get_index_timeseries(
        shapely_geom,
        date_start: str,
        date_end: str,
        mission: str,
        index_name: str,
        use_cloud_mask: bool = True,
        tier: int = 1,
        reducer: str = "median",
        min_valid_pct: float = 0,
        aoi_area_m2: float = None,
    ):
        """One mission's index time series as a DataFrame via agrigee_lite's
        ``download_single_sits`` (server-side ``computeFeatures``, no download).
        Columns include ``timestamp`` (datetime) and the index column (the
        agrigee key). Returns an empty DataFrame if the range misses the
        mission's lifespan.

        ``min_valid_pct`` drops low-coverage dates so the plotted series matches
        the available-date list (both filter on the same valid-pixel threshold).
        """
        import pandas as pd
        from agrigee_lite.get.sits import download_single_sits

        index_key = LANDSAT_INDEX_KEYS.get(index_name, "ndvi")
        sat = LandsatService._build_sr_sat(
            mission, use_cloud_mask, tier, indices={index_key},
            min_valid_pct=min_valid_pct, aoi_area_m2=aoi_area_m2,
        )

        # Clip the request to this mission's lifespan ∩ the requested range so a
        # range that only partly (or doesn't) cover a mission is handled cleanly
        # — non-intersecting missions are skipped, partial ones query only their
        # valid sub-window.
        sat_start, sat_end = sat.startDate[:10], sat.endDate[:10]
        clip_start = max(date_start, sat_start)
        clip_end = min(date_end, sat_end)
        if clip_end <= clip_start:
            return pd.DataFrame()
        try:
            df = download_single_sits(
                shapely_geom, clip_start, clip_end, sat, reducers={reducer}
            )
        except ValueError:
            # Requested period does not intersect this mission's range.
            return pd.DataFrame()
        if df is None or df.empty or index_key not in df.columns:
            return pd.DataFrame()
        return df

    @staticmethod
    def get_index_timeseries_df(
        shapely_geom,
        date_start: str,
        date_end: str,
        index_name: str,
        use_cloud_mask: bool = True,
        tier: int = 1,
        reducer: str = "median",
        min_valid_pct: float = 0,
        aoi_area_m2: float = None,
        missions: list = None,
    ):
        """Combined index time series across the selected missions (default: all
        registered satellites) as a single DataFrame with columns ``dates``,
        ``AOI_average`` and ``mission``, sorted by date. Shaped for the plotly
        renderer reused from the optical page (``view/sar_plot.render_chart_html``)."""
        import pandas as pd

        index_key = LANDSAT_INDEX_KEYS.get(index_name, "ndvi")
        frames = []
        for mission in (missions or MISSIONS):
            try:
                df = LandsatService.get_index_timeseries(
                    shapely_geom,
                    date_start,
                    date_end,
                    mission,
                    index_name,
                    use_cloud_mask,
                    tier,
                    reducer,
                    min_valid_pct=min_valid_pct,
                    aoi_area_m2=aoi_area_m2,
                )
            except Exception:
                # One mission failing (range, quota…) must not drop the others.
                continue
            if df.empty or index_key not in df.columns:
                continue
            sub = df[["timestamp", index_key]].dropna()
            if sub.empty:
                continue
            sub = sub.rename(columns={"timestamp": "dates", index_key: "AOI_average"})
            sub["dates"] = pd.to_datetime(sub["dates"]).dt.strftime("%Y-%m-%d")
            sub["mission"] = mission
            frames.append(sub)

        columns = ["dates", "AOI_average", "mission"]
        if not frames:
            return pd.DataFrame(columns=columns)

        out = pd.concat(frames, ignore_index=True)
        return out.sort_values("dates").reset_index(drop=True)

    # -- single-date image builders ---------------------------------------
    @staticmethod
    def get_superres_image_for_date(
        aoi, date, mission, use_cloud_mask=True, tier=1, buffer_m=0,
        min_valid_pct=0, aoi_area_m2=None,
    ):
        """Pan-sharpened real-colour RGB (15 m) for ``date``, clipped to the
        buffered AOI. Bands returned in R, G, B order so the renderer can always
        use (1, 2, 3)."""
        sat = LandsatService._build_superres_sat(
            mission, use_cloud_mask, tier,
            min_valid_pct=min_valid_pct, aoi_area_m2=aoi_area_m2,
        )
        import ee

        collection = sat.imageCollection(LandsatService._single_date_feature(aoi, date))
        image = ee.Image(collection.first())
        red = LandsatService._numeral_band(sat, "red")
        green = LandsatService._numeral_band(sat, "green")
        blue = LandsatService._numeral_band(sat, "blue")
        image = image.select([red, green, blue], ["red", "green", "blue"])
        region = LandsatService._region(aoi, buffer_m)
        return image.clip(region), region, sat.pixelSize

    @staticmethod
    def get_multispectral_image_for_date(
        aoi, date, mission, mode, use_cloud_mask=True, tier=1, buffer_m=0,
        min_valid_pct=0, aoi_area_m2=None,
    ):
        """Three SR bands (30 m) composited per ``mode``, in display order."""
        sat = LandsatService._build_sr_sat(
            mission, use_cloud_mask, tier,
            min_valid_pct=min_valid_pct, aoi_area_m2=aoi_area_m2,
        )
        import ee

        collection = sat.imageCollection(LandsatService._single_date_feature(aoi, date))
        image = ee.Image(collection.first())
        friendly = MULTISPECTRAL_MODES.get(mode, MULTISPECTRAL_MODES["RGB: Real Color"])
        numerals = [LandsatService._numeral_band(sat, b) for b in friendly]
        image = image.select(numerals, ["r", "g", "b"])
        region = LandsatService._region(aoi, buffer_m)
        return image.clip(region), region, sat.pixelSize

    @staticmethod
    def get_index_image_for_date(
        aoi, date, mission, index_name, use_cloud_mask=True, tier=1, buffer_m=0,
        min_valid_pct=0, aoi_area_m2=None,
    ):
        """Single-band vegetation index (30 m, SR) for ``date``."""
        index_key = LANDSAT_INDEX_KEYS.get(index_name, "ndvi")
        sat = LandsatService._build_sr_sat(
            mission, use_cloud_mask, tier, indices={index_key},
            min_valid_pct=min_valid_pct, aoi_area_m2=aoi_area_m2,
        )
        import ee

        collection = sat.imageCollection(LandsatService._single_date_feature(aoi, date))
        image = ee.Image(collection.first())
        numeral = LandsatService._numeral_index(sat, index_key)
        image = image.select([numeral], ["index"])
        region = LandsatService._region(aoi, buffer_m)
        return image.clip(region), region, sat.pixelSize

    # -- download wrappers -------------------------------------------------
    @staticmethod
    def _download(image, region, scale, filename, output_folder, band_names=None) -> str:
        url = image.getDownloadURL(
            {
                "scale": scale,
                "region": region.bounds().getInfo(),
                "format": "GeoTIFF",
                "crs": "EPSG:4326",
            }
        )
        response = requests.get(url, timeout=300)
        if not response.ok:
            raise RuntimeError(
                f"Landsat download failed (HTTP {response.status_code}): "
                f"{response.reason}"
            )

        base_dir = (
            output_folder
            if (output_folder and os.path.isdir(output_folder))
            else tempfile.gettempdir()
        )
        output_path = LandsatService._unique_path(base_dir, filename)
        with open(output_path, "wb") as f:
            f.write(response.content)

        if band_names:
            LandsatService._set_band_names(output_path, band_names)
        return output_path

    @staticmethod
    def _slug(mission: str) -> str:
        return mission.replace(" ", "")

    @staticmethod
    def download_superres_for_date(
        aoi, date, mission, use_cloud_mask=True, tier=1, buffer_m=0, output_folder=None,
        min_valid_pct=0, aoi_area_m2=None,
    ) -> str:
        image, region, scale = LandsatService.get_superres_image_for_date(
            aoi, date, mission, use_cloud_mask, tier, buffer_m,
            min_valid_pct=min_valid_pct, aoi_area_m2=aoi_area_m2,
        )
        return LandsatService._download(
            image,
            region,
            scale,
            f"{LandsatService._slug(mission)}_SuperRes_{date}.tiff",
            output_folder,
            band_names=["red", "green", "blue"],
        )

    @staticmethod
    def download_multispectral_for_date(
        aoi, date, mission, mode, use_cloud_mask=True, tier=1, buffer_m=0, output_folder=None,
        min_valid_pct=0, aoi_area_m2=None,
    ) -> str:
        image, region, scale = LandsatService.get_multispectral_image_for_date(
            aoi, date, mission, mode, use_cloud_mask, tier, buffer_m,
            min_valid_pct=min_valid_pct, aoi_area_m2=aoi_area_m2,
        )
        return LandsatService._download(
            image,
            region,
            scale,
            f"{LandsatService._slug(mission)}_RGB_{date}.tiff",
            output_folder,
        )

    @staticmethod
    def download_index_for_date(
        aoi, date, mission, index_name, use_cloud_mask=True, tier=1, buffer_m=0, output_folder=None,
        min_valid_pct=0, aoi_area_m2=None,
    ) -> str:
        image, region, scale = LandsatService.get_index_image_for_date(
            aoi, date, mission, index_name, use_cloud_mask, tier, buffer_m,
            min_valid_pct=min_valid_pct, aoi_area_m2=aoi_area_m2,
        )
        return LandsatService._download(
            image,
            region,
            scale,
            f"{LandsatService._slug(mission)}_{index_name}_{date}.tiff",
            output_folder,
        )

    # -- batch super-res download (pure-asyncio fan-out) ------------------
    @staticmethod
    def download_superres_batch(
        aoi,
        dated_missions,
        use_cloud_mask=True,
        tier=1,
        buffer_m=0,
        output_folder=None,
        progress_cb=None,
        cancel_cb=None,
        min_valid_pct=0,
        aoi_area_m2=None,
    ):
        """Download the pan-sharpened super-res RGB (15 m, TOA) of every
        ``(date, mission)`` pair in parallel.

        Each scene is requested as a single multiband GeoTIFF in R, G, B order —
        identical output to ``download_superres_for_date`` — so no zip extraction
        or band merging is needed.

        The whole per-scene pipeline (blocking EE ``getDownloadURL`` round-trip +
        ``requests.get`` byte transfer + write) runs concurrently using pure
        asyncio: each blocking scene is offloaded with ``asyncio.to_thread`` and a
        ``Semaphore`` caps the in-flight count, so the event loop never blocks.
        This drops the previous dependency on ``agrigee_lite``'s aria2 downloader
        (and its native ``aria2c`` binary), which upstream has removed.

        ``progress_cb(completed, total)`` is invoked as downloads finish.
        ``cancel_cb() -> bool`` is polled; returning True stops queuing and
        waiting. Returns the list of written file paths (one per scene that
        downloaded successfully).
        """
        import asyncio

        pairs = list(dated_missions)
        if not pairs:
            return []

        base_dir = (
            output_folder
            if (output_folder and os.path.isdir(output_folder))
            else tempfile.gettempdir()
        )

        # Cap simultaneous EE round-trips / byte transfers. Matches the fan-out
        # previously used for aria2 enqueue.
        max_parallel = 40

        def _cancelled() -> bool:
            return cancel_cb is not None and cancel_cb()

        def _download_one(date, mission):
            """Full blocking pipeline for one scene; runs in a worker thread via
            ``asyncio.to_thread``. Returns the written path or None if the scene
            could not be resolved/downloaded (it is skipped, not fatal)."""
            return LandsatService.download_superres_for_date(
                aoi, date, mission, use_cloud_mask, tier, buffer_m,
                output_folder=base_dir,
                min_valid_pct=min_valid_pct, aoi_area_m2=aoi_area_m2,
            )

        async def _fetch(date, mission, semaphore, counter):
            async with semaphore:
                if _cancelled():
                    return None
                try:
                    path = await asyncio.wait_for(
                        asyncio.to_thread(_download_one, date, mission),
                        timeout=420,
                    )
                except Exception:
                    path = None
                counter["done"] += 1
                if progress_cb is not None:
                    progress_cb(counter["done"], len(pairs))
                return path

        async def _run():
            semaphore = asyncio.Semaphore(max_parallel)
            counter = {"done": 0}
            results = await asyncio.gather(*[
                _fetch(date, mission, semaphore, counter)
                for date, mission in pairs
            ])
            return [path for path in results if path is not None]

        return asyncio.run(_run())

    # -- fs / metadata utilities ------------------------------------------
    @staticmethod
    def _unique_path(folder: str, filename: str) -> str:
        path = os.path.join(folder, filename)
        if not os.path.exists(path):
            return path
        stem, ext = os.path.splitext(filename)
        i = 1
        while os.path.exists(os.path.join(folder, f"{stem}_{i}{ext}")):
            i += 1
        return os.path.join(folder, f"{stem}_{i}{ext}")

    @staticmethod
    def _set_band_names(file_path: str, band_names: list):
        if gdal is None:
            return
        try:
            dataset = gdal.Open(file_path, gdal.GA_Update)
            if dataset is None:
                return
            for i in range(1, min(dataset.RasterCount + 1, len(band_names) + 1)):
                band = dataset.GetRasterBand(i)
                if band is not None:
                    band.SetDescription(band_names[i - 1])
            dataset = None
        except Exception:
            pass
