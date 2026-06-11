# -*- coding: utf-8 -*-
"""
DEM controller for RAVI QGIS plugin.

Orchestrates DEM operations, AOI management, and coordinates between
services for dataset loading and layer rendering.
"""

from qgis.core import QgsProject, QgsCoordinateTransform
from qgis.PyQt.QtCore import QTimer, QCoreApplication

from ..renderers.base_maps import add_google_hybrid_layer
from ..tools.aoi_draw_tool import start_draw_aoi
from ..services.aoi_service import AOIService
from ..renderers.dem_renderer import DEMRenderer
from ..managers.dataset_manager import DatasetManager
from ..services.dem_registry import DEMRegistry
from ..workers.dem_worker import DatasetAvailabilityWorker, DemDownloadWorker


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


class DEMCtrl:
    """
    Orchestrates DEM operations and coordinates between services.

    Manages AOI-based dataset loading, DEM service calls, and layer
    management across the plugin.
    """

    _LAYER_DEBOUNCE_MS = 300
    _CANVAS_SCALE_FACTOR = 1.8

    def __init__(self, dialog, gee_service, interface):
        self.dialog = dialog
        self.gee_service = gee_service
        self.interface = interface

        self.current_aoi = None
        self.current_aoi_bbox = None

        self._pending_layer = None
        self._dem_worker: DemDownloadWorker | None = None
        self._dataset_worker: DatasetAvailabilityWorker | None = None
        self._dem_btn_text: str | None = None
        self._draw_tool = None

        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(self._LAYER_DEBOUNCE_MS)
        self._debounce_timer.timeout.connect(self._load_aoi_for_pending_layer)

    def _is_passive_ee_init_error(self, error):

        return (
            not self.gee_service.is_authenticated
            and "Earth Engine client library not initialized" in str(error)
        )

    def _clear_aoi(self):
        self.current_aoi = None
        self.current_aoi_bbox = None

    def _apply_buffer(self, aoi, buffer_distance: int):

        if buffer_distance == 0:
            return aoi
        return aoi.map(lambda feature: feature.buffer(buffer_distance).bounds())

    def handle_dem_service(self, interface):
        """Download the selected DEM and load it into QGIS."""

        if not self.gee_service.is_authenticated:
            self.dialog.pop_message(
                _tr(
                    "Authentication is required to download DEM data. "
                    "Please go to the Auth page and validate your Google Cloud project ID."
                ),
                "warning",
            )
            return

        if not self.current_aoi:
            self.dialog.pop_message(
                _tr("No AOI selected. Please select a layer first."), "warning"
            )
            return

        dataset_name = self.dialog.dem_combo.currentData()
        if not dataset_name:
            self.dialog.pop_message(_tr("No dataset selected."), "warning")
            return

        if self._dem_worker is not None and self._dem_worker.isRunning():
            return

        output_folder = self.dialog.folder_input.text().strip() or None
        aoi = self._apply_buffer(self.current_aoi, self.dialog.buffer_slider.value())

        self._set_dem_busy(True)
        self._dem_worker = DemDownloadWorker(aoi, dataset_name, output_folder)
        self._dem_worker.finished.connect(self._on_dem_downloaded)
        self._dem_worker.failed.connect(self._on_dem_failed)
        self._dem_worker.start()

    def _set_dem_busy(self, busy: bool):

        btn = self.dialog.btn_download_dem
        if busy:
            self._dem_btn_text = self._dem_btn_text or btn.text()
            btn.setText(_tr("Downloading…"))
        else:
            btn.setText(self._dem_btn_text or btn.text())
        btn.setEnabled(not busy)

    def _on_dem_downloaded(self, dem_path: str, dataset_name: str):
        self._set_dem_busy(False)
        worker, self._dem_worker = self._dem_worker, None
        if worker:
            worker.deleteLater()
        try:
            DEMRenderer.load_dem_to_qgis(dem_path, dataset_name)
            self.interface.messageBar().pushMessage(
                "FARM tools", _tr("DEM '%s' loaded successfully.") % dataset_name
            )
        except Exception as e:
            self.dialog.pop_message(str(e), "warning")

    def _on_dem_failed(self, message):
        self._set_dem_busy(False)
        worker, self._dem_worker = self._dem_worker, None
        if worker:
            worker.deleteLater()
        self.dialog.pop_message(message, "warning")

    def handle_layer_changed(self, layer):

        self._debounce_timer.stop()
        self._clear_aoi()

        if not layer or not layer.isValid() or not self.gee_service.is_authenticated:
            if not layer or not layer.isValid():
                self.dialog.dem_combo.clear()
            return

        self._zoom_to_layer(layer)
        self._pending_layer = layer
        self._debounce_timer.start()

    def _zoom_to_layer(self, layer):

        canvas = self.interface.mapCanvas()
        transform = QgsCoordinateTransform(
            layer.crs(),
            canvas.mapSettings().destinationCrs(),
            QgsProject.instance(),
        )
        extent = transform.transformBoundingBox(layer.extent())
        extent.scale(self._CANVAS_SCALE_FACTOR)
        canvas.setExtent(extent)
        canvas.refresh()

    def _load_aoi_for_pending_layer(self):

        layer = self._pending_layer
        if not layer or not layer.isValid() or not self.gee_service.is_authenticated:
            return

        try:
            self.current_aoi, self.current_aoi_bbox = (
                AOIService.get_ee_feature_colection_from_layer(layer)
            )
            self.load_available_datasets()
        except Exception as e:
            if not self._is_passive_ee_init_error(e):
                self.dialog.pop_message(str(e), "warning")

    def load_available_datasets(self):

        combobox = self.dialog.dem_combo
        combobox.clear()

        if not self.gee_service.is_authenticated:
            for dataset in DEMRegistry().list_datasets():
                combobox.addItem(dataset.name, dataset.name)
            return

        if not self.current_aoi:
            return


        combobox.blockSignals(True)
        combobox.addItem(_tr("Checking available datasets…"))
        combobox.setEnabled(False)
        combobox.blockSignals(False)

        self._dataset_worker = DatasetAvailabilityWorker(
            self.current_aoi, self.current_aoi_bbox
        )
        self._dataset_worker.finished.connect(self._on_datasets_ready)
        self._dataset_worker.failed.connect(self._on_datasets_failed)
        self._dataset_worker.start()

    def _on_datasets_ready(self, names):
        worker, self._dataset_worker = self._dataset_worker, None
        if worker:
            worker.deleteLater()

        combobox = self.dialog.dem_combo
        combobox.blockSignals(True)
        combobox.clear()
        for name in names:
            combobox.addItem(name, name)
        combobox.setEnabled(True)
        combobox.blockSignals(False)
        self.on_dataset_changed()

    def _on_datasets_failed(self, message: str):

        worker, self._dataset_worker = self._dataset_worker, None
        if worker:
            worker.deleteLater()

        combobox = self.dialog.dem_combo
        combobox.blockSignals(True)
        combobox.clear()
        combobox.setEnabled(True)
        combobox.blockSignals(False)
        if not self._is_passive_ee_init_error(message):
            self.dialog.pop_message(message, "warning")

    def on_dataset_changed(self):
        """Update the dataset info panel when the selected dataset changes."""
        DatasetManager.update_dataset_info(self.dialog.dem_combo, self.dialog.dem_info)

    def handle_hybrid_layer(self):

        add_google_hybrid_layer()
        self.interface.messageBar().pushMessage(
            "FARM tools", _tr("Google Hybrid Layer loaded successfully")
        )

    def handle_draw_aoi(self):
        """Toggle rectangular AOI drawing on the canvas."""

        canvas = self.interface.mapCanvas()

        if self._draw_tool is not None and canvas.mapTool() is self._draw_tool:
            canvas.unsetMapTool(self._draw_tool)
            self._draw_tool = None
            return
        self._draw_tool = start_draw_aoi(
            self.interface, self.dialog.layer_combo, self.dialog.btn_draw_aoi
        )
