# -*- coding: utf-8 -*-
"""Map-click coordinate capture for the ClimaPlots page ("clicking mode").

Sibling of ``tools/canvas_marker_tool.py`` (Field Guide): instead of
permanently hijacking the QGIS map tool, this is an explicit, toggleable
capture mode. ``enable(slot)`` remembers the user's current map tool and
switches to a point-emitter; ``disable()`` restores it. Two slots are
supported (primary and comparison) so each point keeps its own colored
marker; a click moves the marker for the active slot and the mode stays on
until toggled off.
"""
import logging

from qgis.PyQt.QtCore import QCoreApplication, QObject, Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
)
from qgis.gui import QgsMapToolEmitPoint, QgsVertexMarker

logger = logging.getLogger(__name__)


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


SLOT_PRIMARY = "A"
SLOT_COMPARISON = "B"

_PRIMARY_COLOR = QColor(255, 0, 0)
_SLOT_COLOR = {SLOT_PRIMARY: _PRIMARY_COLOR, SLOT_COMPARISON: QColor(0, 90, 255)}

_MARKER_SIZE_PX = 12
_MARKER_PEN_PX = 4
_HINT_DURATION_S = 3
# Four decimals of a degree is roughly 11 m — finer than any pixel the
# ClimaPlots datasets resolve, and short enough to read in the coordinate box.
_COORD_DECIMALS = 4


class CanvasClickTool(QObject):
    """Toggleable point capture with per-slot markers + previous-tool restore."""

    point_picked = pyqtSignal(float, float, str)  # longitude, latitude, slot

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self._tool = None
        self._previous_tool = None
        self._slot = SLOT_PRIMARY
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

    def enable(self, slot=SLOT_PRIMARY):
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
                level=Qgis.Info, duration=_HINT_DURATION_S,
            )
        except Exception:
            logger.debug(
                "Failed to show 'click a point' message bar hint", exc_info=True
            )

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
        transform = QgsCoordinateTransform(
            source_crs, self._wgs84, QgsProject.instance()
        )
        wgs84_point = transform.transform(point)
        self._draw_marker(point, self._slot)
        self.point_picked.emit(
            round(wgs84_point.x(), _COORD_DECIMALS),
            round(wgs84_point.y(), _COORD_DECIMALS),
            self._slot,
        )
        # Capture mode stays active until the user toggles it off.

    def _draw_marker(self, map_point, slot):
        self.clear_marker(slot)
        marker = QgsVertexMarker(self.canvas)
        marker.setCenter(map_point)
        marker.setColor(_SLOT_COLOR.get(slot, _PRIMARY_COLOR))
        marker.setIconType(QgsVertexMarker.ICON_X)
        marker.setIconSize(_MARKER_SIZE_PX)
        marker.setPenWidth(_MARKER_PEN_PX)
        self._markers[slot] = marker

    def clear_marker(self, slot=None):
        """Remove the marker for ``slot`` (or all markers when slot is None)."""
        slots = [slot] if slot is not None else list(self._markers)
        for slot_name in slots:
            marker = self._markers.pop(slot_name, None)
            if marker is None:
                continue
            try:
                self.canvas.scene().removeItem(marker)
            except Exception:
                logger.debug(
                    "Failed to remove vertex marker for slot %s from canvas scene",
                    slot_name,
                    exc_info=True,
                )
