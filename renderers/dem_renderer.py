# -*- coding: utf-8 -*-
"""
DEM rendering and styling module.

Handles DEM layer loading and rendering with Magma color scheme.
"""

from qgis.core import QgsRasterLayer

from .raster_renderer_utils import RasterRendererUtils


class DEMRenderer:
    """Handles DEM rendering and layer styling with color ramps."""

    @staticmethod
    def load_dem_to_qgis(path: str, dataset_name: str) -> QgsRasterLayer:

        raster_layer = RasterRendererUtils.load_pseudocolor_raster(
            path, dataset_name, band_index=1, color_ramp_name="Magma", at_top=True
        )

        if raster_layer is None:
            raise RuntimeError("Failed to load DEM into QGIS.")

        return raster_layer
