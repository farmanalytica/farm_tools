# -*- coding: utf-8 -*-
"""
Background worker for the Optical point / per-feature analysis.

Extracts a vegetation-index time series for one or more geometries (clicked
points or polygon features) off the UI thread, emitting one result per geometry
as it completes so lines can appear incrementally.
"""

import ee
from qgis.PyQt.QtCore import pyqtSignal

from ..services.optical_service import OpticalService
from .background_worker import EarthEngineWorker

_DEFAULT_REDUCER = "mean"


class OpticalAnalysisWorker(EarthEngineWorker):
    # label, rows ([{date, value}]), color_hex
    series_ready = pyqtSignal(str, object, str)
    finished = pyqtSignal()

    def __init__(self, jobs, params):
        """``jobs``: list of ``{"label", "geojson", "reducer", "color"}``.
        ``params``: shared ``{date_start, date_end, index_name, apply_scl,
        invalid_scl_values}``.
        """
        super().__init__()
        self._jobs = jobs
        self._params = params

    def work(self):
        for job in self._jobs:
            rows = OpticalService.get_geometry_time_series(
                geometry=ee.Geometry(job["geojson"]),
                date_start=self._params["date_start"],
                date_end=self._params["date_end"],
                index_name=self._params["index_name"],
                apply_scl=self._params["apply_scl"],
                invalid_scl_values=self._params["invalid_scl_values"],
                reducer=job.get("reducer", _DEFAULT_REDUCER),
                custom_expression=self._params.get("custom_expression"),
            )
            self.series_ready.emit(job["label"], rows, job.get("color", ""))
        self.finished.emit()
