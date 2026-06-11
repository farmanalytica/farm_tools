# -*- coding: utf-8 -*-
"""
Point capture for the Optical (Sentinel-2) point analysis.

A ``QgsMapToolEmitPoint`` subclass that drops a coloured dot on each click and
reports the clicked location in WGS84 to a callback. Dot colours are pulled from
the same palette the multi-series plot uses, so the dot on the map matches the
line colour in the chart.

Improvement over the legacy CoordinateCaptureTool: colours come from the shared
plot palette (deterministic, dot == line) instead of random bright colours, the
tool keeps no global state, and ``clear`` removes every rubber band in one call.
"""

from qgis.PyQt.QtCore import QCoreApplication, Qt
from qgis.PyQt.QtGui import QColor
from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsProject,
    QgsWkbTypes,
)


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


_WGS84 = "EPSG:4326"


class PointCaptureTool(QgsMapToolEmitPoint):
    """Click to drop a coloured sample point; report it in WGS84.

    Args:
        canvas: the map canvas.
        on_point: callback ``(lon, lat, index, color_hex)`` invoked on each
            click, with ``index`` the 0-based capture order and ``color_hex``
            the dot colour (matching the plot line).
        palette: list of CSS hex colours cycled per point (shared with the
            multi-series chart so dot colour == line colour).
    """

    def __init__(self, canvas, on_point, palette):
        super().__init__(canvas)
        self.canvas = canvas
        self._on_point = on_point
        self._palette = palette
        self._bands = []
        self._wgs84 = QgsCoordinateReferenceSystem(_WGS84)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def canvasReleaseEvent(self, event):
        point_project = self.toMapCoordinates(event.pos())
        index = len(self._bands)
        color_hex = self._palette[index % len(self._palette)]

        self._draw_dot(point_project, color_hex)

        point_wgs84 = self._to_wgs84(point_project)
        if self._on_point is not None:
            self._on_point(point_wgs84.x(), point_wgs84.y(), index, color_hex)

    def _to_wgs84(self, point_project):
        project_crs = self.canvas.mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(
            project_crs, self._wgs84, QgsProject.instance()
        )
        return transform.transform(point_project)

    def _draw_dot(self, point_project, color_hex):
        band = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry)
        band.setColor(QColor(color_hex))
        band.setWidth(6)
        band.setIcon(QgsRubberBand.ICON_CIRCLE)
        band.setToGeometry(QgsGeometry.fromPointXY(point_project), None)
        band.show()
        self._bands.append(band)

    def clear(self):
        """Remove every captured dot from the canvas."""
        for band in self._bands:
            band.reset(QgsWkbTypes.PointGeometry)
        self._bands = []

    def deactivate(self):
        super().deactivate()
