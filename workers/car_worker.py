# -*- coding: utf-8 -*-
"""
Background worker for the CAR analysis page, so the dialog stays responsive
during the two network round-trips to the public CAR registry bucket.

The worker does network + disk I/O only. Building the KML and loading the layer
into QGIS stay on the main thread (the caller handles that on completion).
"""

from qgis.PyQt.QtCore import pyqtSignal

from ..services.car_service import CarService
from .background_worker import BackgroundWorker


class CarFetchWorker(BackgroundWorker):
    """Resolves a CAR code to a GeoJSON file off the UI thread."""

    finished = pyqtSignal(str, str)  # geojson_path, car_code

    def __init__(self, car_code, output_folder, proxy):
        super().__init__()
        self._car_code = car_code
        self._output_folder = output_folder
        self._proxy = proxy

    def work(self):
        geojson_path = CarService.fetch_geojson(
            self._car_code,
            output_folder=self._output_folder,
            proxy=self._proxy,
        )
        self.finished.emit(geojson_path, CarService.normalize_code(self._car_code))
