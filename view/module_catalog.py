# -*- coding: utf-8 -*-
"""
The one description of what a FARM tools module is.

The welcome hub, the sidebar rail and the Customize dialog all need the same
facts about each module — its key, its display name, its blurb, its icon and
whether it needs a Google Earth Engine sign-in. Those facts live here, once,
as named fields rather than tuple positions.

This module is pure data: which modules exist and what they are called.
Which ones a given user sees, and in what order, is :mod:`module_prefs`.
"""

from typing import NamedTuple, Optional

AUTH_KEY = "auth"
FARM_GREEN = "#1b6b39"


class Module(NamedTuple):
    """One tool in the plugin, as the hub and the rail both see it.

    ``brand_name`` is the product name a single-module build ships under; it
    defaults to ``name`` for the modules whose two names agree.
    """

    key: str
    name: str
    description: str
    nav_attr: str
    needs_gee: bool
    logo_svg: Optional[str] = None
    sidebar_logo_svg: Optional[str] = None
    brand_name: Optional[str] = None

    @property
    def flavor_label(self) -> str:
        """The plugin-menu name when this module ships on its own."""
        return self.brand_name or self.name


MODULES = (
    Module(
        "optical", "RAVI (Sentinel-2)",
        "Per-date vegetation-index time series (NDVI, EVI, NDRE…) with cloud masking",
        "show_optical_page", True,
        logo_svg="ravi.svg", sidebar_logo_svg="ravi_white_background.svg",
        brand_name="RAVI",
    ),
    Module(
        "landsat", "Multi-Satellite",
        "Pan-sharpened 15 m Landsat 7/8/9 imagery and multi-mission index series",
        "show_landsat_page", True,
    ),
    Module(
        "sysi", "Bare Soil",
        "Bare-soil reflectance composite (GEOS3) from cloud-free pixels for soil mapping",
        "show_sysi_page", True,
    ),
    Module(
        "radar", "Radar (SAR) data",
        "Sentinel-1 VV/VH backscatter time series — cloud-independent monitoring",
        "show_radar_page", True,
        logo_svg="sentinel1.svg", sidebar_logo_svg="sentinel1.svg",
        brand_name="AGLgis",
    ),
    Module(
        "download", "EasyDEM",
        "Fetch terrain elevation models (SRTM, Copernicus…) clipped to your area",
        "_nav_to_dem", True,
        logo_svg="easydem.svg", sidebar_logo_svg="easydem.svg",
    ),
    Module(
        "climaplots", "ClimaPlots",
        "Climate trends, indices and thermo diagrams from NASA POWER daily data",
        "show_climaplots_page", False,
        logo_svg="climaplots.svg", sidebar_logo_svg="climaplots.svg",
    ),
    Module(
        "fieldguide", "Field Guide",
        "Per-feature and per-point analysis with adjustable buffer and value extraction",
        "show_fieldguide_page", False,
        logo_svg="fieldguide.svg", sidebar_logo_svg="fieldguide.svg",
    ),
    Module(
        "mapbiomas", "MapBiomas",
        "Brazilian land-use/land-cover by year plus pasture-to-crop transition mapping",
        "show_mapbiomas_page", True,
    ),
    Module(
        "mzones", "Management Zones",
        "Cluster yield/index/soil rasters into within-field zones (PCA + KMeans)",
        "show_mzones_page", False,
    ),
    Module(
        "car", "Análise CAR",
        "Fetch a registered rural property boundary by its Brazilian CAR code",
        "show_car_page", False,
    ),
    Module(
        AUTH_KEY, "GEE Configuration",
        "Connect to Google Earth Engine — sign in and set your project ID",
        "show_auth_page", True,
    ),
)

BY_KEY = {module.key: module for module in MODULES}

# Auth is pinned (always shown, never reordered), so it is not manageable.
MANAGEABLE_KEYS = tuple(
    module.key for module in MODULES if module.key != AUTH_KEY
)

FLAVOR_LABELS = {
    module.key: module.flavor_label
    for module in MODULES
    if module.key != AUTH_KEY
}


def label(key, default=""):
    """The display name for ``key``."""
    module = BY_KEY.get(key)
    return module.name if module else default
