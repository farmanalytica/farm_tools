# -*- coding: utf-8 -*-
"""
Controller for the SYSI (Synthetic Soil Image) page.

Wires the UI inputs in ``view/sysi.py`` to the GEOS3 pipeline implemented in
``services/sysi_service.py``.  Follows the same patterns as ``sar_ctrl.py``:
  • AOI is extracted on the main thread and passed to a QThread worker.
  • The worker emits ``finished``/``failed``; the controller loads the result
    into QGIS and updates the UI.
  • The generate button is disabled while the worker is running to prevent
    concurrent submissions.
"""

import os
import tempfile

from qgis.PyQt.QtCore import Qt, QCoreApplication
from qgis.core import (
    QgsContrastEnhancement,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsLayerTreeLayer,
    QgsMultiBandColorRenderer,
    QgsProject,
    QgsRasterLayer,
)

from ..services.aoi_service import AOIService
from ..workers.sysi_worker import SYSIWorker
from ..managers.settings_manager import SettingsManager
from ..tools.aoi_draw_tool import start_draw_aoi

try:
    WAIT_CURSOR = Qt.CursorShape.WaitCursor
except AttributeError:
    WAIT_CURSOR = Qt.WaitCursor

_CANVAS_SCALE_FACTOR = 1.5


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


# Band order in the exported GeoTIFF: Blue=1, Green=2, Red=3, ...
# Natural-colour RGB: Red=band3, Green=band2, Blue=band1
_RGB_RED_BAND = 3
_RGB_GREEN_BAND = 2
_RGB_BLUE_BAND = 1


class SYSICtrl:
    """Handles user interactions on the SYSI page."""

    def __init__(self, dialog, interface=None, gee_service=None):
        self.dialog = dialog
        self.interface = interface
        self.gee_service = gee_service

        self.aoi = None
        self._worker: SYSIWorker | None = None
        self._draw_tool = None
        self._generate_btn_text: str | None = None

    # ------------------------------------------------------------------
    # Worker lifecycle
    # ------------------------------------------------------------------

    def _release_worker(self):
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    # ------------------------------------------------------------------
    # AOI helpers
    # ------------------------------------------------------------------

    def handle_draw_aoi(self):
        """Toggle rectangular AOI drawing on the canvas."""
        canvas = self.interface.mapCanvas()
        if self._draw_tool is not None and canvas.mapTool() is self._draw_tool:
            canvas.unsetMapTool(self._draw_tool)
            self._draw_tool = None
            return
        self._draw_tool = start_draw_aoi(
            self.interface,
            self.dialog.sysi_layer_combo,
            self.dialog.sysi_btn_draw_aoi,
        )

    def handle_layer_changed(self, layer=None):
        """Zoom the map canvas to the newly selected AOI layer."""
        if layer is None:
            layer = self.dialog.sysi_layer_combo.currentLayer()
        if not layer or not layer.isValid() or not self.interface:
            return
        canvas = self.interface.mapCanvas()
        transform = QgsCoordinateTransform(
            layer.crs(),
            canvas.mapSettings().destinationCrs(),
            QgsProject.instance(),
        )
        extent = transform.transformBoundingBox(layer.extent())
        extent.scale(_CANVAS_SCALE_FACTOR)
        canvas.setExtent(extent)
        canvas.refresh()

    def _download_aoi(self):
        """Return the AOI expanded (or cropped) by the buffer slider value.

        Values within ±3 m are snapped to 0 (dead zone) to avoid accidental
        tiny offsets.  Returns the original AOI when the slider is at 0 or
        when no AOI has been set yet.
        """
        slider = getattr(self.dialog, "sysi_buffer_slider", None)
        raw = slider.value() if slider is not None else 0
        meters = 0 if -3 <= raw <= 3 else raw
        if not meters or self.aoi is None:
            return self.aoi
        return self.aoi.map(lambda feature: feature.buffer(meters).bounds())

    # ------------------------------------------------------------------
    # Generate SYSI
    # ------------------------------------------------------------------

    def _read_params(self):
        """Collect all UI parameter values into a dict."""
        months = [
            m for m, chk in self.dialog.sysi_month_checks.items()
            if chk.isChecked()
        ]

        return {
            "start_date": self.dialog.sysi_date_start.date().toString("yyyy-MM-dd"),
            "end_date": self.dialog.sysi_date_end.date().toString("yyyy-MM-dd"),
            "cloud_threshold": self.dialog.sysi_cloud_slider.value(),
            "ndvi_thres": [
                self.dialog.sysi_ndvi_range_slider.low(),
                self.dialog.sysi_ndvi_range_slider.high(),
            ],
            "nbr_thres": [
                self.dialog.sysi_nbr_range_slider.low(),
                self.dialog.sysi_nbr_range_slider.high(),
            ],
            "selected_months": months,
        }

    def handle_generate_sysi(self):
        """Validate inputs and launch the GEOS3 pipeline worker."""
        if self._worker is not None and self._worker.isRunning():
            return

        if self.gee_service and not self.gee_service.is_authenticated:
            self.dialog.pop_message(
                _tr(
                    "Authentication is required to generate SYSI data. "
                    "Please go to the Auth page and validate your Google Cloud "
                    "project ID."
                ),
                "warning",
            )
            return

        layer = self.dialog.sysi_layer_combo.currentLayer()
        if not layer:
            self.dialog.pop_message(_tr("Select an AOI layer."), "warning")
            return

        params = self._read_params()

        if not params["selected_months"]:
            self.dialog.pop_message(
                _tr("Select at least one month."), "warning"
            )
            return

        start_qdate = self.dialog.sysi_date_start.date()
        end_qdate = self.dialog.sysi_date_end.date()
        if start_qdate >= end_qdate:
            self.dialog.pop_message(
                _tr("End date must be after start date."), "warning"
            )
            return

        try:
            aoi, _bbox = AOIService.get_ee_feature_colection_from_layer(
                layer, use_selected_features=False
            )
        except Exception as exc:
            self.dialog.pop_message(str(exc), "warning")
            return

        self.aoi = aoi
        params["output_folder"] = (
            SettingsManager.load_download_folder() or tempfile.gettempdir()
        )
        params["label"] = "SYSI"

        self._set_generate_busy(True)

        self._worker = SYSIWorker(self._download_aoi(), params)
        self._worker.finished.connect(self._on_sysi_done)
        self._worker.failed.connect(self._on_sysi_failed)
        self._worker.start()

    def _set_generate_busy(self, busy: bool):
        btn = self.dialog.sysi_btn_generate
        if busy:
            self._generate_btn_text = self._generate_btn_text or btn.text()
            btn.setText(_tr("Generating…"))
        else:
            btn.setText(self._generate_btn_text or btn.text())
        btn.setEnabled(not busy)

    def _on_sysi_done(self, output_path: str, label: str):
        self._set_generate_busy(False)
        self._release_worker()

        self._load_sysi_to_qgis(output_path, label)

        if self.interface:
            filename = os.path.basename(output_path)
            self.interface.messageBar().pushMessage(
                "FARM tools",
                _tr("SYSI '%s' generated and loaded into QGIS.") % filename,
            )

    def _on_sysi_failed(self, message: str):
        self._set_generate_busy(False)
        self._release_worker()
        self.dialog.pop_message(message, "warning")

    # ------------------------------------------------------------------
    # QGIS layer loading
    # ------------------------------------------------------------------

    def _load_sysi_to_qgis(self, path: str, label: str):
        """Load the SYSI GeoTIFF as a natural-colour RGB layer in QGIS.

        Band layout in the exported file:
          1 Blue · 2 Green · 3 Red · 4 Rededge2 · 5 NIR
          6 SWIR1 · 7 SWIR2 · 8 NDVI · 9 NBR2

        The renderer uses R=3, G=2, B=1 (natural colour) with a 2–98 %
        cumulative-cut contrast enhancement, matching the pattern used by
        ``SARRenderer._create_rgb_composite``.
        """
        layer = QgsRasterLayer(path, label)
        if not layer.isValid():
            self.dialog.pop_message(
                _tr("Failed to load SYSI raster into QGIS."), "warning"
            )
            return

        layer.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

        renderer = QgsMultiBandColorRenderer(
            layer.dataProvider(),
            _RGB_RED_BAND,
            _RGB_GREEN_BAND,
            _RGB_BLUE_BAND,
        )

        try:
            provider = layer.dataProvider()
            from qgis.utils import iface as _iface
            canvas = _iface.mapCanvas() if _iface else None
            extent = canvas.extent() if canvas else layer.extent()
            if not extent.intersects(layer.extent()):
                extent = layer.extent()

            for band_idx, set_fn in [
                (_RGB_RED_BAND, renderer.setRedContrastEnhancement),
                (_RGB_GREEN_BAND, renderer.setGreenContrastEnhancement),
                (_RGB_BLUE_BAND, renderer.setBlueContrastEnhancement),
            ]:
                min_max = provider.cumulativeCut(band_idx, 0.02, 0.98, extent, 250000)
                ce = QgsContrastEnhancement(provider.dataType(band_idx))
                ce.setContrastEnhancementAlgorithm(
                    QgsContrastEnhancement.StretchToMinimumMaximum
                )
                ce.setMinimumValue(min_max[0])
                ce.setMaximumValue(min_max[1])
                set_fn(ce)
        except Exception:
            pass

        layer.setRenderer(renderer)
        QgsProject.instance().addMapLayer(layer, False)
        root = QgsProject.instance().layerTreeRoot()
        root.insertChildNode(0, QgsLayerTreeLayer(layer))
        layer.triggerRepaint()
