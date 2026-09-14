# -*- coding: utf-8 -*-
"""
Background workers for the DEM page's network-bound triggers, so the dialog
stays responsive during GEE dataset-availability checks and DEM downloads.
"""

from qgis.PyQt.QtCore import pyqtSignal

from ..services.dem_service import DEMService
from ..services.dem_registry import DEMRegistry
from .background_worker import BackgroundWorker


class DatasetAvailabilityWorker(BackgroundWorker):
    """Checks, off the UI thread, which catalog datasets cover the AOI."""

    finished = pyqtSignal(list)

    def __init__(self, aoi, aoi_bbox):
        super().__init__()
        self._aoi = aoi
        self._aoi_bbox = aoi_bbox

    def work(self):
        registry = DEMRegistry()
        geometry = self._aoi.geometry()
        names = [
            dataset.name
            for dataset in registry.list_datasets()
            if registry.has_coverage(
                dataset.name, geometry, aoi_bbox=self._aoi_bbox
            )
        ]
        self.finished.emit(names)


class DemDownloadWorker(BackgroundWorker):
    """Downloads the selected DEM off the UI thread. Loading the result into
    QGIS stays on the main thread (the caller handles that on completion)."""

    finished = pyqtSignal(str, str)

    def __init__(self, aoi, dataset_name, output_folder):
        super().__init__()
        self._aoi = aoi
        self._dataset_name = dataset_name
        self._output_folder = output_folder

    def work(self):
        dem_path = DEMService.download_dem(
            self._aoi, self._dataset_name, output_folder=self._output_folder
        )
        self.finished.emit(dem_path, self._dataset_name)
