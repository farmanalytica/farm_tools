# -*- coding: utf-8 -*-
"""
Renderer for the CAR analysis page.

Takes the GeoJSON FeatureCollection saved by ``CarService``, writes a KML copy
into the same (download) folder, loads it as a vector layer, applies a simple
outline style and adds it to the project. Must run on the main thread.
"""

import os

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsCoordinateTransformContext,
    QgsProject,
    QgsSingleSymbolRenderer,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

from ..tools.map_canvas import zoom_canvas_to_layer
from .aoi_style import build_aoi_fill_symbol
from .raster_renderer_utils import RasterRendererUtils


_CAR_ZOOM_PADDING = 1.2


class CarRenderer:
    """Converts the CAR GeoJSON to KML and loads it into QGIS."""

    @staticmethod
    def load_car_to_qgis(geojson_path: str, car_code: str, interface=None):
        """Write a KML next to ``geojson_path``, load it and return the layer.

        Returns the loaded ``QgsVectorLayer`` (the KML on disk). Raises
        ``RuntimeError`` on any failure.
        """
        source = QgsVectorLayer(geojson_path, car_code, "ogr")
        if not source.isValid():
            raise RuntimeError("Could not read the downloaded CAR geometry.")

        kml_path = os.path.splitext(geojson_path)[0] + ".kml"
        kml_path = CarRenderer._unique_path(kml_path)

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "KML"
        options.fileEncoding = "UTF-8"
        options.layerName = car_code
        # KML is WGS84-only; reproject if the source somehow is not 4326.
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        if source.crs() != wgs84:
            options.ct = QgsCoordinateTransform(
                source.crs(), wgs84, QgsProject.instance()
            )

        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            source, kml_path, QgsCoordinateTransformContext(), options
        )
        if result[0] != QgsVectorFileWriter.NoError:
            raise RuntimeError("Failed to write the CAR KML file: %s" % result[1])

        layer = QgsVectorLayer(kml_path, "CAR %s" % car_code, "ogr")
        if not layer.isValid():
            raise RuntimeError("The CAR KML layer could not be loaded.")

        CarRenderer._style(layer)
        RasterRendererUtils.add_layer_to_project(layer)
        layer.triggerRepaint()

        if interface is not None:
            CarRenderer._zoom_to_layer(layer, interface)

        return layer

    @staticmethod
    def _style(layer):
        """Give the CAR boundary the same look as a drawn AOI.

        KML layers load with a ``QgsEmbeddedSymbolRenderer`` (no ``symbol()``),
        so replace the renderer outright with our own single-symbol fill.
        """
        layer.setRenderer(QgsSingleSymbolRenderer(build_aoi_fill_symbol()))

    @staticmethod
    def _zoom_to_layer(layer, interface):
        zoom_canvas_to_layer(interface.mapCanvas(), layer, _CAR_ZOOM_PADDING)

    @staticmethod
    def _unique_path(path: str) -> str:
        if not os.path.exists(path):
            return path
        base, ext = os.path.splitext(path)
        counter = 1
        while True:
            candidate = f"{base}_{counter}{ext}"
            if not os.path.exists(candidate):
                return candidate
            counter += 1
