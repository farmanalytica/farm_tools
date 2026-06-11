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


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


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
        self._wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        # Optional callback invoked when another tool displaces the capture
        # tool, so the owning controller can sync its toggle button.
        self.on_deactivated = None

    def _ensure_map_tool(self):
        """Lazily create the click tool and connect once."""
        if self._map_tool is None:
            self._map_tool = QgsMapToolEmitPoint(self.canvas)
            self._map_tool.canvasClicked.connect(self._on_canvas_clicked)
            self._map_tool.deactivated.connect(self._on_tool_deactivated)

    def is_active(self):
        """Return True when the capture tool currently owns the canvas."""
        return self._map_tool is not None and self.canvas.mapTool() is self._map_tool

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
            duration=3,
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

        source_crs = self.canvas.mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(source_crs, self._wgs84, QgsProject.instance())
        wgs84_point = transform.transform(point)
        self._store_coordinate_with_visuals(point, wgs84_point.x(), wgs84_point.y())

    def add_wgs84_point(self, latitude, longitude):
        """Add a point from manual WGS84 input and render visuals on canvas."""
        destination_crs = self.canvas.mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(self._wgs84, destination_crs, QgsProject.instance())
        map_point = transform.transform(QgsPointXY(longitude, latitude))
        self._store_coordinate_with_visuals(map_point, longitude, latitude)

    def add_wgs84_points(self, lat_lon_pairs):
        """Add multiple WGS84 points while emitting only one UI refresh."""
        lat_lon_pairs = list(lat_lon_pairs)
        if not lat_lon_pairs:
            return 0

        destination_crs = self.canvas.mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(self._wgs84, destination_crs, QgsProject.instance())

        for latitude, longitude in lat_lon_pairs:
            map_point = transform.transform(QgsPointXY(longitude, latitude))
            self._store_coordinate_with_visuals(
                map_point,
                longitude,
                latitude,
                emit_signal=False,
                show_message=False,
            )

        self.canvas.refresh()
        self.coordinates_changed.emit(list(self.coordinates))
        return len(lat_lon_pairs)

    def _store_coordinate_with_visuals(
        self,
        map_point,
        longitude,
        latitude,
        emit_signal=True,
        show_message=True,
    ):
        """Persist WGS84 tuple, draw marker/label, and show capture feedback."""
        self.coordinates.append((longitude, latitude))

        marker = QgsVertexMarker(self.canvas)
        marker.setCenter(map_point)
        marker.setColor(QColor(220, 40, 40))
        marker.setIconType(QgsVertexMarker.ICON_X)
        marker.setIconSize(12)
        marker.setPenWidth(3)
        self._markers.append(marker)

        label_text = str(len(self.coordinates))
        annotation = QgsTextAnnotation()
        annotation.setMapPosition(map_point)
        annotation.setFrameOffsetFromReferencePointMm(QPointF(4, -5))

        # High-contrast badge so numbers stay readable over any basemap.
        # We style the document itself for compatibility across QGIS builds.
        doc = QTextDocument()
        doc.setHtml(
            '<div style="font-weight:700; font-size:12pt; color:#111; '
            'text-align:center; background:#FFFFFF; border:1px solid #222; '
            'border-radius:4px; padding:1px 4px;">{}</div>'.format(label_text)
        )
        annotation.setDocument(doc)

        frame_width_mm = 8 + max(0, len(label_text) - 1) * 2
        annotation.setFrameSizeMm(QSizeF(frame_width_mm, 8))

        label_item = QgsMapCanvasAnnotationItem(annotation, self.canvas)
        self._label_items.append(label_item)

        if show_message:
            self.iface.messageBar().pushMessage(
                _tr("FARM tools"),
                _tr("Point {0} saved in WGS84: ({1:.6f}, {2:.6f})").format(
                    len(self.coordinates), longitude, latitude
                ),
                level=Qgis.Success,
                duration=2,
            )
        if emit_signal:
            self.coordinates_changed.emit(list(self.coordinates))

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
            marker = self._markers.pop()
            self.canvas.scene().removeItem(marker)

        if self._label_items:
            label_item = self._label_items.pop()
            self.canvas.scene().removeItem(label_item)

        self.coordinates_changed.emit(list(self.coordinates))
        return True

    def remove_at(self, index):
        """Remove a point by index and rebuild labels so numbering stays contiguous."""
        if index < 0 or index >= len(self.coordinates):
            return False

        remaining_points = [
            (latitude, longitude)
            for point_index, (longitude, latitude) in enumerate(self.coordinates)
            if point_index != index
        ]

        self._clear_visuals()
        self.coordinates = []

        if remaining_points:
            self.add_wgs84_points(remaining_points)
        else:
            self.coordinates_changed.emit(list(self.coordinates))
        return True
