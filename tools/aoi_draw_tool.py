# -*- coding: utf-8 -*-
"""
Interactive AOI drawing for RAVI.

Provides a click-to-add-vertex polygon map tool plus a single
``start_draw_aoi`` entry point shared by the DEM, RAVI, SAR, Landsat, SYSI
and MapBiomas pages, so the draw-on-canvas behaviour is defined once.
Clicking a sequence of points on the canvas and closing the shape creates a
WGS84 in-memory polygon layer that is added to the project and selected in
the page's AOI combo.

The drawn polygon is written immediately as an ESRI Shapefile into the
currently selected download folder and that on-disk layer is loaded into
the project.

UX over a plain emit-point tool:
  * live translucent preview, with the next edge following the cursor,
  * double-click, right-click, or clicking the first point closes the polygon,
  * Backspace/Delete undoes the last point,
  * Esc cancels the in-progress polygon,
  * the tool deactivates itself once finished and restores the previous tool,
  * a hint and a success message are shown on the QGIS message bar.
"""

import os
import tempfile
from dataclasses import dataclass
from typing import Callable, Optional

from qgis.PyQt.QtCore import Qt, QTimer, QCoreApplication, QVariant
from qgis.PyQt.QtGui import QColor
from qgis.gui import QgsMapTool, QgsRubberBand, QgsVertexMarker
from qgis.core import (
    Qgis,
    QgsProject,
    QgsGeometry,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsWkbTypes,
    QgsCoordinateTransform,
    QgsCoordinateReferenceSystem,
)

from ..managers.settings_manager import SettingsManager
from ..renderers.aoi_style import build_aoi_fill_symbol
from ..view.styles import STYLE_BTN_SECONDARY, STYLE_BTN_DRAW_ACTIVE


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


_WGS84 = "EPSG:4326"
_FILL = QColor(27, 107, 57, 60)
_STROKE = QColor(255, 0, 0, 220)
_MIN_VERTICES = 3
_CLOSE_TOLERANCE_PX = 10
_BAND_WIDTH_PX = 2
_VERTEX_MARKER_SIZE_PX = 8
_VERTEX_MARKER_PEN_PX = 2


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
    suffix = 2
    while os.path.exists(subdir):
        name = "{}_{}".format(base, suffix)
        subdir = os.path.join(folder, name)
        suffix += 1
    os.makedirs(subdir, exist_ok=True)
    path = os.path.join(subdir, base + ".shp")
    return path, name


def _style_aoi(layer):
    layer.renderer().setSymbol(build_aoi_fill_symbol())


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


@dataclass
class AoiDrawCallbacks:
    """Hooks ``PolygonAoiTool`` fires as the polygon is drawn.

    ``on_created`` receives the saved AOI layer (or ``None`` when saving
    failed), ``on_point_added`` the running vertex count, and
    ``on_too_few_points`` the current count and the required minimum.
    """

    on_created: Optional[Callable] = None
    on_finished: Optional[Callable] = None
    on_point_added: Optional[Callable] = None
    on_too_few_points: Optional[Callable] = None


class PolygonAoiTool(QgsMapTool):
    """Click to add vertices, double-click/right-click to close the AOI polygon."""

    def __init__(self, canvas, callbacks=None):
        super().__init__(canvas)
        self.canvas = canvas
        self.callbacks = callbacks or AoiDrawCallbacks()
        self._points = []
        self._markers = []
        self._band = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
        self._band.setFillColor(_FILL)
        self._band.setStrokeColor(_STROKE)
        self._band.setWidth(_BAND_WIDTH_PX)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def canvasPressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if len(self._points) >= _MIN_VERTICES and self._near_first_point(event.pos()):
                self._finish()
                return
            point = self.toMapCoordinates(event.pos())
            self._points.append(point)
            self._add_vertex_marker(point)
            self._draw_band(self._points)
            if self.callbacks.on_point_added:
                self.callbacks.on_point_added(len(self._points))
        elif event.button() == Qt.MouseButton.RightButton:
            self._finish()

    def canvasMoveEvent(self, event):
        if not self._points:
            return
        if len(self._points) >= _MIN_VERTICES and self._near_first_point(event.pos()):
            preview = self._points + [self._points[0]]
        else:
            preview = self._points + [self.toMapCoordinates(event.pos())]
        self._draw_band(preview)

    def _near_first_point(self, pos):
        """True when ``pos`` (canvas pixels) is close enough to the first vertex to close the polygon there."""
        first_screen = self.toCanvasCoordinates(self._points[0])
        dx = pos.x() - first_screen.x()
        dy = pos.y() - first_screen.y()
        return (dx * dx + dy * dy) <= _CLOSE_TOLERANCE_PX ** 2

    def canvasDoubleClickEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        # canvasPressEvent already appended a vertex (and its marker) for the
        # second click of the double-click; drop both so the finish doesn't
        # duplicate a point.
        if self._points:
            self._points.pop()
            self._remove_last_vertex_marker()
        self._finish()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._clear()
            QTimer.singleShot(0, lambda: self.canvas.unsetMapTool(self))
        elif event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            if self._points:
                self._points.pop()
                self._remove_last_vertex_marker()
                self._draw_band(self._points)
                if self.callbacks.on_point_added:
                    self.callbacks.on_point_added(len(self._points))

    def _draw_band(self, points):
        if len(points) < 2:
            self._band.reset(QgsWkbTypes.PolygonGeometry)
            return
        self._band.setToGeometry(QgsGeometry.fromPolygonXY([points]), None)
        self._band.show()

    def _add_vertex_marker(self, point):
        """Drop a small circle marker at ``point``."""
        marker = QgsVertexMarker(self.canvas)
        marker.setCenter(point)
        marker.setColor(_STROKE)
        marker.setIconType(QgsVertexMarker.ICON_CIRCLE)
        marker.setIconSize(_VERTEX_MARKER_SIZE_PX)
        marker.setPenWidth(_VERTEX_MARKER_PEN_PX)
        self._markers.append(marker)

    def _remove_last_vertex_marker(self):
        if self._markers:
            self.canvas.scene().removeItem(self._markers.pop())

    def _clear_vertex_markers(self):
        for marker in self._markers:
            self.canvas.scene().removeItem(marker)
        self._markers = []

    def _finish(self):
        if len(self._points) < _MIN_VERTICES:
            if self.callbacks.on_too_few_points:
                self.callbacks.on_too_few_points(len(self._points), _MIN_VERTICES)
            return
        points = self._points
        self._clear()
        self._emit_layer(points)
        QTimer.singleShot(0, lambda: self.canvas.unsetMapTool(self))

    def _emit_layer(self, points_project):
        geom = QgsGeometry.fromPolygonXY([points_project])
        if not geom.isGeosValid():
            geom = geom.makeValid()
        if geom is None or geom.isEmpty():
            if self.callbacks.on_created:
                self.callbacks.on_created(None)
            return
        project_crs = self.canvas.mapSettings().destinationCrs()
        wgs84 = QgsCoordinateReferenceSystem(_WGS84)
        if project_crs != wgs84:
            xform = QgsCoordinateTransform(project_crs, wgs84, QgsProject.instance())
            geom.transform(xform)
        layer = create_aoi_shapefile(geom)
        if self.callbacks.on_created:
            self.callbacks.on_created(layer)

    def _clear(self):
        self._points = []
        self._clear_vertex_markers()
        self._band.reset(QgsWkbTypes.PolygonGeometry)

    def deactivate(self):
        self._clear()
        super().deactivate()
        if self.callbacks.on_finished:
            self.callbacks.on_finished()


def start_draw_aoi(interface, target_combo, button=None, before_select=None):
    """Begin interactive polygon-AOI drawing.

    ``before_select``, if given, is called right before the finished AOI
    layer is set on ``target_combo`` — callers use it to suppress the
    zoom-to-layer their page normally does on ``layerChanged``, since the
    user just drew the AOI and is already looking at it; jumping the canvas
    to its exact extent right after would disrupt the flow into the next
    step. It fires synchronously within the same ``setLayer`` call, so
    there's nothing to reset if the draw is cancelled instead of finished.
    """
    canvas = interface.mapCanvas()
    message_bar = interface.messageBar()

    banner = message_bar.createMessage(
        _tr("Draw AOI mode"),
        _tr(
            "Click to add points, double-click, right-click, or click the "
            "first point to finish. Backspace to undo the last point, Esc "
            "to cancel."
        ),
    )
    message_bar.pushWidget(banner, Qgis.Info)

    if button is not None:
        button.setStyleSheet(STYLE_BTN_DRAW_ACTIVE)

    def on_created(layer):
        if layer is None:
            message_bar.pushMessage(
                "FARM tools",
                _tr("Could not save the drawn AOI. Try again."),
                level=Qgis.Warning,
            )
            return
        if target_combo is not None:
            if before_select is not None:
                before_select()
            target_combo.setLayer(layer)
        message_bar.pushMessage(
            "FARM tools",
            _tr("AOI saved to '{}' and selected.").format(layer.source()),
            level=Qgis.Success,
        )

    def on_point_added(count):
        if count >= _MIN_VERTICES:
            hint = _tr("Right-click, double-click, or click the first point to finish.")
        else:
            hint = _tr("Add at least {0} more point(s).").format(_MIN_VERTICES - count)
        message_bar.pushMessage(
            "FARM tools",
            _tr("{0} point(s) added. {1}").format(count, hint),
            level=Qgis.Info,
            duration=2,
        )

    def on_too_few_points(count, minimum):
        message_bar.pushMessage(
            "FARM tools",
            _tr("Add at least {0} points before finishing (currently {1}).").format(
                minimum, count
            ),
            level=Qgis.Warning,
            duration=3,
        )

    previous_tool = canvas.mapTool()

    def on_finished():
        message_bar.popWidget(banner)
        if button is not None:
            button.setStyleSheet(STYLE_BTN_SECONDARY)
        if previous_tool is not None and previous_tool is not tool:
            canvas.setMapTool(previous_tool)

    tool = PolygonAoiTool(
        canvas,
        AoiDrawCallbacks(
            on_created=on_created,
            on_finished=on_finished,
            on_point_added=on_point_added,
            on_too_few_points=on_too_few_points,
        ),
    )
    canvas.setMapTool(tool)
    return tool
