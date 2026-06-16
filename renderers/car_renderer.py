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
    QgsFillSymbol,
    QgsProject,
    QgsSingleSymbolRenderer,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

from .raster_renderer_utils import RasterRendererUtils


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
        RasterRendererUtils.add_layer_to_project(layer, at_top=True)
        layer.triggerRepaint()

        if interface is not None:
            CarRenderer._zoom_to_layer(layer, interface)

        return layer

    @staticmethod
    def _style(layer):
        """Translucent green fill with a solid FARM-green outline.

        KML layers load with a ``QgsEmbeddedSymbolRenderer`` (no ``symbol()``),
        so replace the renderer outright with our own single-symbol fill.
        """
        symbol = QgsFillSymbol.createSimple(
            {
                "color": "31,107,58,50",
                "outline_color": "31,107,58,255",
                "outline_width": "0.6",
            }
        )
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))

    @staticmethod
    def _zoom_to_layer(layer, interface):
        canvas = interface.mapCanvas()
        transform = QgsCoordinateTransform(
            layer.crs(),
            canvas.mapSettings().destinationCrs(),
            QgsProject.instance(),
        )
        extent = transform.transformBoundingBox(layer.extent())
        extent.scale(1.2)
        canvas.setExtent(extent)
        canvas.refresh()

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
