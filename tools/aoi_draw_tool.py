# -*- coding: utf-8 -*-
"""
Interactive AOI drawing for RAVI.

Provides a rectangle map tool plus a single ``start_draw_aoi`` entry point
shared by the DEM and SAR pages, so the draw-on-canvas behaviour is defined
once. Dragging on the canvas creates a WGS84 in-memory polygon layer that is
added to the project and selected in the page's AOI combo.

The drawn box is written immediately as an ESRI Shapefile into the currently
selected download folder and that on-disk layer is loaded into the project.

UX over a plain emit-point tool:
  * live translucent preview while dragging,
  * Shift constrains the box to a square,
  * Esc cancels the in-progress box,
  * the tool deactivates itself after one box and restores the previous tool,
  * a hint and a success message are shown on the QGIS message bar.
"""

import os
import tempfile

from qgis.PyQt.QtCore import Qt, QTimer, QCoreApplication, QVariant
from qgis.PyQt.QtGui import QColor
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.core import (
    Qgis,
    QgsProject,
    QgsPointXY,
    QgsRectangle,
    QgsGeometry,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsFillSymbol,
    QgsWkbTypes,
    QgsCoordinateTransform,
    QgsCoordinateReferenceSystem,
)

from ..managers.settings_manager import SettingsManager
from ..view.styles import STYLE_BTN_SECONDARY, STYLE_BTN_DRAW_ACTIVE


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


_WGS84 = "EPSG:4326"
_FILL = QColor(27, 107, 57, 60)
_STROKE = QColor(255, 0, 0, 220)


def _target_folder():
    """Currently selected download folder, or the system temp dir."""
    folder = (SettingsManager.load_download_folder() or "").strip()
    if folder and os.path.isdir(folder):
        return folder
    return tempfile.gettempdir()


def _unique_shp_path(folder, base="drawn_aoi"):
    """Return a shapefile path inside a fresh per-draw subfolder, plus its name.
    ``<folder>/<base>[_n]/``
    """
    name = base
    subdir = os.path.join(folder, name)
    n = 2
    while os.path.exists(subdir):
        name = "{}_{}".format(base, n)
        subdir = os.path.join(folder, name)
        n += 1
    os.makedirs(subdir, exist_ok=True)
    path = os.path.join(subdir, base + ".shp")
    return path, name


def _style_aoi(layer):
    symbol = QgsFillSymbol.createSimple(
        {
            "color": "27,107,57,40",
            "outline_color": "255,0,0,255",
            "outline_width": "0.6",
        }
    )
    layer.renderer().setSymbol(symbol)


def create_aoi_shapefile(geom_wgs84):
    """
    Write ``geom_wgs84`` as a single-feature WGS84 shapefile into the selected
    download folder, load it into the project, and return the loaded layer.

    Returns ``None`` if writing the shapefile fails.
    """
    folder = _target_folder()
    path, name = _unique_shp_path(folder)

    fields = QgsFields()
    fields.append(QgsField("id", QVariant.Int))

    feature = QgsFeature(fields)
    feature.setAttribute("id", 1)
    feature.setGeometry(geom_wgs84)

    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "ESRI Shapefile"
    options.fileEncoding = "UTF-8"

    writer = QgsVectorFileWriter.create(
        path,
        fields,
        QgsWkbTypes.Polygon,
        QgsCoordinateReferenceSystem(_WGS84),
        QgsProject.instance().transformContext(),
        options,
    )
    if writer.hasError() != QgsVectorFileWriter.NoError:
        del writer
        return None
    writer.addFeature(feature)
    del writer

    layer = QgsVectorLayer(path, name, "ogr")
    if not layer.isValid():
        return None
    _style_aoi(layer)
    QgsProject.instance().addMapLayer(layer)
    return layer


class RectangleAoiTool(QgsMapTool):
    """Drag to draw a rectangular AOI; emits a WGS84 memory polygon layer."""

    def __init__(self, canvas, on_created=None, on_finished=None):
        super().__init__(canvas)
        self.canvas = canvas
        self.on_created = on_created
        self.on_finished = on_finished
        self._start = None
        self._dragging = False
        self._band = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
        self._band.setFillColor(_FILL)
        self._band.setStrokeColor(_STROKE)
        self._band.setWidth(2)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def canvasPressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._start = self.toMapCoordinates(event.pos())
        self._dragging = True

    def canvasMoveEvent(self, event):
        if not self._dragging or self._start is None:
            return
        self._draw_band(self._corner(event))

    def canvasReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or not self._dragging:
            return
        self._dragging = False
        end = self._corner(event)
        start = self._start
        self._clear()
        if start is None:
            return
        rect = QgsRectangle(start, end)
        if rect.width() <= 0 or rect.height() <= 0:
            return
        self._emit_layer(rect)
        QTimer.singleShot(0, lambda: self.canvas.unsetMapTool(self))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._clear()
            QTimer.singleShot(0, lambda: self.canvas.unsetMapTool(self))

    def _corner(self, event):
        """End corner in map CRS, squared off when Shift is held."""
        point = self.toMapCoordinates(event.pos())
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier and self._start:
            dx = point.x() - self._start.x()
            dy = point.y() - self._start.y()
            side = max(abs(dx), abs(dy))
            x = self._start.x() + (side if dx >= 0 else -side)
            y = self._start.y() + (side if dy >= 0 else -side)
            return QgsPointXY(x, y)
        return point

    def _draw_band(self, end):
        rectangle = QgsRectangle(self._start, end)
        self._band.setToGeometry(QgsGeometry.fromRect(rectangle), None)
        self._band.show()

    def _emit_layer(self, rectangle_project):
        geom = QgsGeometry.fromRect(rectangle_project)
        project_crs = self.canvas.mapSettings().destinationCrs()
        wgs84 = QgsCoordinateReferenceSystem(_WGS84)
        if project_crs != wgs84:
            xform = QgsCoordinateTransform(project_crs, wgs84, QgsProject.instance())
            geom.transform(xform)
        layer = create_aoi_shapefile(geom)
        if self.on_created:
            self.on_created(layer)

    def _clear(self):
        self._dragging = False
        self._start = None
        self._band.reset(QgsWkbTypes.PolygonGeometry)

    def deactivate(self):
        self._clear()
        super().deactivate()
        if self.on_finished:
            self.on_finished()


def start_draw_aoi(interface, target_combo, button=None):
    """Begin interactive rectangle-AOI drawing"""
    canvas = interface.mapCanvas()
    message_bar = interface.messageBar()

    banner = message_bar.createMessage(
        _tr("Draw AOI mode"),
        _tr("Drag on the map to draw a box. Hold Shift for a square, Esc to cancel."),
    )
    message_bar.pushWidget(banner, Qgis.Info)

    if button is not None:
        button.setStyleSheet(STYLE_BTN_DRAW_ACTIVE)

    def on_created(layer):
        if layer is None:
            message_bar.pushMessage(
                "FARM tools",
                _tr("Failed to save AOI shapefile to the download folder."),
                level=Qgis.Warning,
            )
            return
        if target_combo is not None:
            target_combo.setLayer(layer)
        message_bar.pushMessage(
            "FARM tools",
            _tr("AOI saved to '{}' and selected.").format(layer.source()),
            level=Qgis.Success,
        )

    previous_tool = canvas.mapTool()

    def on_finished():
        message_bar.popWidget(banner)
        if button is not None:
            button.setStyleSheet(STYLE_BTN_SECONDARY)
        if previous_tool is not None and previous_tool is not tool:
            canvas.setMapTool(previous_tool)

    tool = RectangleAoiTool(canvas, on_created=on_created, on_finished=on_finished)
    canvas.setMapTool(tool)
    return tool
