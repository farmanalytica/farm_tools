# -*- coding: utf-8 -*-
"""Map-click coordinate capture for the ClimaPlots page ("clicking mode").

Sibling of ``tools/canvas_marker_tool.py`` (Field Guide): instead of
permanently hijacking the QGIS map tool, this is an explicit, toggleable
capture mode. ``enable(slot)`` remembers the user's current map tool and
switches to a point-emitter; ``disable()`` restores it. Two slots are
supported ("A" and "B") so a primary point and a comparison point can each
keep their own colored marker; a click moves the marker for the active slot
and the mode stays on until toggled off.
"""
from qgis.PyQt.QtCore import QCoreApplication, QObject, Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
)
from qgis.gui import QgsMapToolEmitPoint, QgsVertexMarker


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


_SLOT_COLOR = {"A": QColor(255, 0, 0), "B": QColor(0, 90, 255)}


class CanvasClickTool(QObject):
    """Toggleable point capture with per-slot markers + previous-tool restore."""

    point_picked = pyqtSignal(float, float, str)  # longitude, latitude, slot

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self._tool = None
        self._previous_tool = None
        self._slot = "A"
        self._markers = {}  # slot -> QgsVertexMarker
        self._wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        # Optional callback invoked when another tool displaces the capture
        # tool, so the owning controller can sync its toggle buttons.
        self.on_deactivated = None

    def _ensure_tool(self):
        if self._tool is None:
            self._tool = QgsMapToolEmitPoint(self.canvas)
            self._tool.canvasClicked.connect(self._on_clicked)
            self._tool.deactivated.connect(self._on_tool_deactivated)

    def is_active(self):
        return self._tool is not None and self.canvas.mapTool() is self._tool

    def enable(self, slot="A"):
        """Activate capture mode for ``slot``, remembering the current map tool."""
        self._slot = slot
        self._ensure_tool()
        if self.canvas.mapTool() is not self._tool:
            self._previous_tool = self.canvas.mapTool()
        self.canvas.setMapTool(self._tool)
        try:
            self.iface.messageBar().pushMessage(
                _tr("FARM tools"),
                _tr("Click a point on the map to set the coordinate."),
                level=Qgis.Info, duration=3,
            )
        except Exception:
            pass

    def disable(self):
        """Deactivate capture mode and restore the previous map tool."""
        if self._tool is not None and self.canvas.mapTool() is self._tool:
            if self._previous_tool is not None:
                self.canvas.setMapTool(self._previous_tool)
            else:
                self.canvas.unsetMapTool(self._tool)
        self._previous_tool = None

    def _on_tool_deactivated(self):
        """Notify the owner when the canvas tool is displaced or released."""
        if self.on_deactivated is not None:
            self.on_deactivated()

    def _on_clicked(self, point, button):
        if button != Qt.MouseButton.LeftButton:
            return
        source_crs = self.canvas.mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(source_crs, self._wgs84, QgsProject.instance())
        wgs = transform.transform(point)
        self._draw_marker(point, self._slot)
        self.point_picked.emit(round(wgs.x(), 4), round(wgs.y(), 4), self._slot)
        # Capture mode stays active until the user toggles it off.

    def _draw_marker(self, map_point, slot):
        self.clear_marker(slot)
        marker = QgsVertexMarker(self.canvas)
        marker.setCenter(map_point)
        marker.setColor(_SLOT_COLOR.get(slot, QColor(255, 0, 0)))
        marker.setIconType(QgsVertexMarker.ICON_X)
        marker.setIconSize(12)
        marker.setPenWidth(4)
        self._markers[slot] = marker

    def clear_marker(self, slot=None):
        """Remove the marker for ``slot`` (or all markers when slot is None)."""
        slots = [slot] if slot is not None else list(self._markers)
        for s in slots:
            marker = self._markers.pop(s, None)
            if marker is not None:
                try:
                    self.canvas.scene().removeItem(marker)
                except Exception:
                    pass
