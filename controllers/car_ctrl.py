# -*- coding: utf-8 -*-
"""
CAR analysis controller for the FARM tools QGIS plugin.

Wires the CAR page: validates the typed code, runs the registry lookup off the
UI thread, and loads the resulting geometry as a KML layer saved to the
configured download folder.
"""

from __future__ import annotations

from qgis.PyQt.QtCore import QCoreApplication

from ..managers.settings_manager import SettingsManager
from ..renderers.car_renderer import CarRenderer
from ..services.car_service import CarService
from ..workers.car_worker import CarFetchWorker


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


class CarCtrl:
    """Orchestrates CAR code lookups and layer loading."""

    def __init__(self, dialog, interface):
        self.dialog = dialog
        self.interface = interface
        self._worker: CarFetchWorker | None = None
        self._btn_text: str | None = None

    def handle_fetch_car(self):
        """Validate the CAR code and download its geometry into QGIS."""
        if self._worker is not None and self._worker.isRunning():
            return

        code = CarService.normalize_code(self.dialog.car_input.text())
        if not code:
            self.dialog.pop_message(_tr("Please type a CAR code."), "warning")
            return
        if not CarService.is_valid_code(code):
            self.dialog.pop_message(
                _tr(
                    "Invalid CAR code. Expected a format like "
                    "GO-5219258-CAE9B45810F4458584BAB4E860CF288E."
                ),
                "warning",
            )
            return

        output_folder = SettingsManager.load_download_folder() or None
        proxy = SettingsManager.get_proxy() or None

        self._set_busy(True)
        self._worker = CarFetchWorker(code, output_folder, proxy)
        self._worker.finished.connect(self._on_fetched)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _set_busy(self, busy: bool):
        btn = self.dialog.btn_fetch_car
        if busy:
            self._btn_text = self._btn_text or btn.text()
            btn.setText(_tr("Fetching…"))
        else:
            btn.setText(self._btn_text or btn.text())
        btn.setEnabled(not busy)
        self.dialog.car_input.setEnabled(not busy)

    def _on_fetched(self, geojson_path: str, car_code: str):
        self._set_busy(False)
        worker, self._worker = self._worker, None
        if worker:
            worker.deleteLater()
        try:
            CarRenderer.load_car_to_qgis(geojson_path, car_code, self.interface)
            self.interface.messageBar().pushMessage(
                "FARM tools", _tr("CAR '%s' loaded successfully.") % car_code
            )
        except Exception as e:
            self.dialog.pop_message(str(e), "warning")

    def _on_failed(self, message: str):
        self._set_busy(False)
        worker, self._worker = self._worker, None
        if worker:
            worker.deleteLater()
        self.dialog.pop_message(message, "warning")
