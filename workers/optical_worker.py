# -*- coding: utf-8 -*-
"""
Background worker for the Sentinel-2 index time series.

Fetches the vegetation-index series for the AOI over the selected date range
off the UI thread. The AOI is extracted on the main thread and passed in.
"""

from qgis.PyQt.QtCore import pyqtSignal

from ..services.optical_service import OpticalService
from .background_worker import EarthEngineWorker

_DEFAULT_INDEX = "NDVI"
_DEFAULT_REDUCER = "mean"


class OpticalWorker(EarthEngineWorker):
    finished = pyqtSignal(object, str)   # rows, index_name

    def __init__(self, aoi, params):
        super().__init__()
        self._aoi = aoi
        self._params = params

    def work(self):
        params = self._params
        index_name = params.get("index_name", _DEFAULT_INDEX)

        data_rows = OpticalService.get_time_series(
            aoi=self._aoi,
            date_start=params.get("date_start"),
            date_end=params.get("date_end"),
            index_name=index_name,
            apply_scl=params.get("apply_scl", False),
            invalid_scl_values=params.get("invalid_scl_values", []),
            custom_expression=params.get("custom_expression"),
            reducer=params.get("reducer", _DEFAULT_REDUCER),
        )
        self.finished.emit(data_rows, index_name)
