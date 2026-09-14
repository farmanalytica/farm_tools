# -*- coding: utf-8 -*-
"""
Map canvas framing shared by the pages that select or produce an AOI layer.

Every page zoomed to its AOI with the same transform-extent-scale-refresh
sequence, each with its own padding factor; the sequence lives here now and
the padding stays a per-page choice.
"""

from qgis.core import QgsCoordinateTransform, QgsProject

DEFAULT_ZOOM_PADDING = 1.5


def zoom_canvas_to_layer(canvas, layer, padding=DEFAULT_ZOOM_PADDING):
    """Fit ``layer``'s extent in ``canvas``, grown by ``padding`` for breathing room."""
    transform = QgsCoordinateTransform(
        layer.crs(),
        canvas.mapSettings().destinationCrs(),
        QgsProject.instance(),
    )
    extent = transform.transformBoundingBox(layer.extent())
    extent.scale(padding)
    canvas.setExtent(extent)
    canvas.refresh()
