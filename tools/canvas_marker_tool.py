# -*- coding: utf-8 -*-
"""Canvas click capture and visual mark management for the Field Guide page.

This module is intentionally isolated from the controller layer so map
interaction logic (tool switching, coordinate capture, marker drawing) can be
reused.
"""

from qgis.PyQt import QtCore
from qgis.PyQt.QtCore import QCoreApplication, QPointF, QSizeF, Qt
from qgis.PyQt.QtGui import QColor, QTextDocument
from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsPointXY,
    QgsProject,
    QgsTextAnnotation,
)
from qgis.gui import QgsMapCanvasAnnotationItem, QgsMapToolEmitPoint, QgsVertexMarker

_WGS84 = "EPSG:4326"

_MARKER_COLOR = QColor(220, 40, 40)
_MARKER_SIZE_PX = 12
_MARKER_PEN_PX = 3

# The numbered badge sits up and to the right of its marker so it never covers
# the point it labels, and widens by one digit's worth per extra digit.
_BADGE_OFFSET_MM = QPointF(4, -5)
_BADGE_HEIGHT_MM = 8
_BADGE_BASE_WIDTH_MM = 8
_BADGE_WIDTH_PER_EXTRA_DIGIT_MM = 2

_ENABLED_HINT_DURATION_S = 3
_POINT_SAVED_DURATION_S = 2


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


def _badge_html(label_text):
    """High-contrast badge markup, styled on the document for QGIS build portability."""
    return (
        '<div style="font-weight:700; font-size:12pt; color:#111; '
        'text-align:center; background:#FFFFFF; border:1px solid #222; '
        'border-radius:4px; padding:1px 4px;">{}</div>'.format(label_text)
    )


class CanvasMarkerTool(QtCore.QObject):
    """Handle map-click point capture and visual feedback on canvas."""

    coordinates_changed = QtCore.pyqtSignal(list)

    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.coordinates = []
        self._markers = []
        self._label_items = []
        self._map_tool = None
        self._previous_map_tool = None
        self._wgs84 = QgsCoordinateReferenceSystem(_WGS84)
        # Optional callback invoked when another tool displaces the capture
        # tool, so the owning controller can sync its toggle button.
        self.on_deactivated = None

    def _ensure_map_tool(self):
        """Lazily create the click tool and connect once."""
        if self._map_tool is None:
            self._map_tool = QgsMapToolEmitPoint(self.canvas)
            self._map_tool.canvasClicked.connect(self._on_canvas_clicked)
            self._map_tool.deactivated.connect(self._on_tool_deactivated)

    def enable(self):
        """Activate capture mode and keep current map tool for later restore."""
        self._ensure_map_tool()
        if self.canvas.mapTool() != self._map_tool:
            self._previous_map_tool = self.canvas.mapTool()
        self.canvas.setMapTool(self._map_tool)
        self.iface.messageBar().pushMessage(
            _tr("FARM tools"),
            _tr("Marking mode enabled. Click on the map to add points."),
            level=Qgis.Info,
            duration=_ENABLED_HINT_DURATION_S,
        )

    def disable(self):
        """Deactivate capture mode and restore previous map tool when possible."""
        if self._map_tool is not None and self.canvas.mapTool() == self._map_tool:
            if self._previous_map_tool is not None:
                self.canvas.setMapTool(self._previous_map_tool)
            else:
                self.canvas.unsetMapTool(self._map_tool)
        self._previous_map_tool = None

    def _on_tool_deactivated(self):
        """Notify the owner when the canvas tool is displaced or released."""
        if self.on_deactivated is not None:
            self.on_deactivated()

    def _on_canvas_clicked(self, point, button):
        """Save click in WGS84, draw marker, and add an incrementing label."""
        if button != Qt.MouseButton.LeftButton:
            return

        transform = self._transform_to_wgs84()
        wgs84_point = transform.transform(point)
        self._add_point(point, wgs84_point.x(), wgs84_point.y())
        self._announce_last_point()
        self.coordinates_changed.emit(list(self.coordinates))

    def add_wgs84_point(self, latitude, longitude):
        """Add a point from manual WGS84 input and render visuals on canvas."""
        map_point = self._transform_from_wgs84().transform(
            QgsPointXY(longitude, latitude)
        )
        self._add_point(map_point, longitude, latitude)
        self._announce_last_point()
        self.coordinates_changed.emit(list(self.coordinates))

    def add_wgs84_points(self, lat_lon_pairs):
        """Add multiple WGS84 points while emitting only one UI refresh."""
        lat_lon_pairs = list(lat_lon_pairs)
        if not lat_lon_pairs:
            return 0

        transform = self._transform_from_wgs84()
        for latitude, longitude in lat_lon_pairs:
            map_point = transform.transform(QgsPointXY(longitude, latitude))
            self._add_point(map_point, longitude, latitude)

        self.canvas.refresh()
        self.coordinates_changed.emit(list(self.coordinates))
        return len(lat_lon_pairs)

    def _transform_to_wgs84(self):
        return QgsCoordinateTransform(
            self.canvas.mapSettings().destinationCrs(),
            self._wgs84,
            QgsProject.instance(),
        )

    def _transform_from_wgs84(self):
        return QgsCoordinateTransform(
            self._wgs84,
            self.canvas.mapSettings().destinationCrs(),
            QgsProject.instance(),
        )

    def _add_point(self, map_point, longitude, latitude):
        """Store the WGS84 pair and draw its marker and numbered badge."""
        self.coordinates.append((longitude, latitude))
        self._draw_marker(map_point)
        self._draw_badge(map_point, str(len(self.coordinates)))

    def _draw_marker(self, map_point):
        marker = QgsVertexMarker(self.canvas)
        marker.setCenter(map_point)
        marker.setColor(_MARKER_COLOR)
        marker.setIconType(QgsVertexMarker.ICON_X)
        marker.setIconSize(_MARKER_SIZE_PX)
        marker.setPenWidth(_MARKER_PEN_PX)
        self._markers.append(marker)

    def _draw_badge(self, map_point, label_text):
        document = QTextDocument()
        document.setHtml(_badge_html(label_text))

        extra_digits = max(0, len(label_text) - 1)
        width_mm = (
            _BADGE_BASE_WIDTH_MM + extra_digits * _BADGE_WIDTH_PER_EXTRA_DIGIT_MM
        )

        annotation = QgsTextAnnotation()
        annotation.setMapPosition(map_point)
        annotation.setFrameOffsetFromReferencePointMm(_BADGE_OFFSET_MM)
        annotation.setDocument(document)
        annotation.setFrameSizeMm(QSizeF(width_mm, _BADGE_HEIGHT_MM))

        self._label_items.append(
            QgsMapCanvasAnnotationItem(annotation, self.canvas)
        )

    def _announce_last_point(self):
        longitude, latitude = self.coordinates[-1]
        self.iface.messageBar().pushMessage(
            _tr("FARM tools"),
            _tr("Point {0} saved in WGS84: ({1:.6f}, {2:.6f})").format(
                len(self.coordinates), longitude, latitude
            ),
            level=Qgis.Success,
            duration=_POINT_SAVED_DURATION_S,
        )

    def clear(self):
        """Remove all marker graphics and reset captured coordinates."""
        self._clear_visuals()
        self.coordinates = []
        self.coordinates_changed.emit(list(self.coordinates))

    def _clear_visuals(self):
        """Remove all marker and label graphics from the map canvas."""
        for marker in self._markers:
            self.canvas.scene().removeItem(marker)

        for label_item in self._label_items:
            self.canvas.scene().removeItem(label_item)

        self._markers = []
        self._label_items = []

    def remove_last(self):
        """Remove only the most recently added mark and coordinate."""
        if not self.coordinates:
            return False

        self.coordinates.pop()

        if self._markers:
            self.canvas.scene().removeItem(self._markers.pop())

        if self._label_items:
            self.canvas.scene().removeItem(self._label_items.pop())

        self.coordinates_changed.emit(list(self.coordinates))
        return True

    def remove_at(self, index):
        """Remove a point by index and rebuild labels so numbering stays contiguous."""
        if index < 0 or index >= len(self.coordinates):
            return False

        surviving_lat_lon = [
            (latitude, longitude)
            for point_index, (longitude, latitude) in enumerate(self.coordinates)
            if point_index != index
        ]

        self._clear_visuals()
        self.coordinates = []

        if surviving_lat_lon:
            self.add_wgs84_points(surviving_lat_lon)
        else:
            self.coordinates_changed.emit(list(self.coordinates))
        return True
