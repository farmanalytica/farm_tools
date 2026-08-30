# -*- coding: utf-8 -*-
"""
SAR rendering.

Turns a downloaded Sentinel-1 GeoTIFF into a styled QGIS layer, either as an
RGB composite of three polarimetric bands or as a single pseudocolor band,
according to the render mode picked on the SAR page.
"""

import logging
from dataclasses import dataclass

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsContrastEnhancement,
    QgsMultiBandColorRenderer,
    QgsRasterLayer,
)
from qgis.utils import iface

from .raster_renderer_utils import PseudocolorStyle, RasterRendererUtils

logger = logging.getLogger(__name__)

BAND_INDEX_MAP = {
    "VV": 1,
    "VH": 2,
    "VV/VH Ratio": 3,
    "RVI": 4,
    "DpRVI": 5,
    "CR": 6,
    "NDPI": 7,
    "PD": 8,
    "DPSVIm": 9,
    "PRVI": 10,
    "mRVI": 11,
}

_RGB_PREFIX = "RGB: "
_BAND_PREFIX = "Band: "
_DEFAULT_RGB_BANDS = ["VV", "VH", "VV/VH Ratio"]
_DEFAULT_RENDER_MODE = _RGB_PREFIX + ", ".join(_DEFAULT_RGB_BANDS)
_DEFAULT_COLOR_RAMP = "Viridis"
_RGB_BAND_COUNT = 3

_SAR_CRS = "EPSG:4326"
# Clip the darkest/brightest 2% before stretching: SAR speckle otherwise
# pins the whole histogram against a handful of outlier pixels.
_CUT_LOWER = 0.02
_CUT_UPPER = 0.98
_CUT_SAMPLE_SIZE = 250000


@dataclass
class SarRenderOptions:
    """How a SAR GeoTIFF should be painted, as chosen on the SAR page."""

    render_mode: str = _DEFAULT_RENDER_MODE
    color_ramp_name: str = _DEFAULT_COLOR_RAMP


def _rgb_band_names(render_mode):
    """The three band names of an ``RGB: a, b, c`` mode, or ``None``."""
    if not render_mode.startswith(_RGB_PREFIX):
        return None
    names = [name.strip() for name in render_mode[len(_RGB_PREFIX):].split(",")]
    if len(names) != _RGB_BAND_COUNT:
        return None
    if not all(name in BAND_INDEX_MAP for name in names):
        return None
    return names


def _single_band_name(render_mode):
    """The band name of a ``Band: x`` mode, or ``None``."""
    if not render_mode.startswith(_BAND_PREFIX):
        return None
    name = render_mode[len(_BAND_PREFIX):].strip()
    return name if name in BAND_INDEX_MAP else None


class SARRenderer:
    """Loads SAR GeoTIFFs into QGIS under the render mode chosen on the page."""

    @staticmethod
    def _stretch_to_visible_range(renderer, layer, band_indexes):
        """Stretch each RGB band over the visible extent, ignoring speckle outliers."""
        provider = layer.dataProvider()
        canvas = iface.mapCanvas()
        extent = canvas.extent() if canvas else layer.extent()
        if not extent.intersects(layer.extent()):
            extent = layer.extent()

        setters = (
            renderer.setRedContrastEnhancement,
            renderer.setGreenContrastEnhancement,
            renderer.setBlueContrastEnhancement,
        )
        for band_index, set_enhancement in zip(band_indexes, setters):
            low, high = provider.cumulativeCut(
                band_index, _CUT_LOWER, _CUT_UPPER, extent, _CUT_SAMPLE_SIZE
            )
            enhancement = QgsContrastEnhancement(provider.dataType(band_index))
            enhancement.setContrastEnhancementAlgorithm(
                QgsContrastEnhancement.StretchToMinimumMaximum
            )
            enhancement.setMinimumValue(low)
            enhancement.setMaximumValue(high)
            set_enhancement(enhancement)

    @staticmethod
    def _create_rgb_composite(path, layer_name, band_names):
        layer = QgsRasterLayer(path, layer_name)
        if not layer.isValid():
            raise RuntimeError("Failed to load SAR image into QGIS.")

        layer.setCrs(QgsCoordinateReferenceSystem(_SAR_CRS))

        band_indexes = [
            BAND_INDEX_MAP.get(name, position)
            for position, name in enumerate(band_names, start=1)
        ]
        renderer = QgsMultiBandColorRenderer(layer.dataProvider(), *band_indexes)

        try:
            SARRenderer._stretch_to_visible_range(renderer, layer, band_indexes)
        except Exception:
            logger.warning("Error applying contrast enhancement", exc_info=True)

        layer.setRenderer(renderer)
        RasterRendererUtils.add_layer_to_project(layer)
        layer.triggerRepaint()
        return layer

    @staticmethod
    def _load_pseudocolor_or_raise(path, layer_name, style):
        layer = RasterRendererUtils.load_pseudocolor_raster(path, layer_name, style)
        if layer is None:
            raise RuntimeError(f"Failed to load SAR image into QGIS from {path}")
        return layer

    @staticmethod
    def load_composite_to_qgis(path, layer_name, color_ramp_name=_DEFAULT_COLOR_RAMP):
        """Load a single-band composite GeoTIFF with a pseudocolor palette."""
        return SARRenderer._load_pseudocolor_or_raise(
            path, layer_name, PseudocolorStyle(color_ramp_name)
        )

    @staticmethod
    def load_sar_to_qgis(path, layer_name, options=None):
        """Load a SAR GeoTIFF under ``options``, falling back to the default RGB trio."""
        options = options or SarRenderOptions()

        rgb_bands = _rgb_band_names(options.render_mode)
        if rgb_bands:
            return SARRenderer._create_rgb_composite(path, layer_name, rgb_bands)

        band_name = _single_band_name(options.render_mode)
        if band_name:
            return SARRenderer._load_pseudocolor_or_raise(
                path,
                f"{layer_name} [{band_name}]",
                PseudocolorStyle(
                    options.color_ramp_name, band_index=BAND_INDEX_MAP[band_name]
                ),
            )

        return SARRenderer._create_rgb_composite(
            path, layer_name, list(_DEFAULT_RGB_BANDS)
        )
