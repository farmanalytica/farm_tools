# -*- coding: utf-8 -*-
"""
Background worker for the Optical point / per-feature analysis.

Extracts a vegetation-index time series for one or more geometries (clicked
points or polygon features) off the UI thread, emitting one result per geometry
as it completes so lines can appear incrementally.

Improvement over the legacy path, which ran every Earth Engine call on the main
thread behind a wait cursor (freezing QGIS): here the work runs in a QThread and
streams results back via signals.
"""

import traceback

import ee
from qgis.PyQt.QtCore import QThread, pyqtSignal

from ..services.optical_service import OpticalService


class OpticalAnalysisWorker(QThread):
    # label, rows ([{date, value}]), color_hex
    series_ready = pyqtSignal(str, object, str)
    finished = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, jobs, params):
        """``jobs``: list of ``{"label", "geojson", "reducer", "color"}``.
        ``params``: shared ``{date_start, date_end, index_name, apply_scl,
        invalid_scl_values}``.
        """
        super().__init__()
        self._jobs = jobs
        self._params = params

    def run(self):
        try:
            for job in self._jobs:
                geometry = ee.Geometry(job["geojson"])
                rows = OpticalService.get_geometry_time_series(
                    geometry=geometry,
                    date_start=self._params["date_start"],
                    date_end=self._params["date_end"],
                    index_name=self._params["index_name"],
                    apply_scl=self._params["apply_scl"],
                    invalid_scl_values=self._params["invalid_scl_values"],
                    reducer=job.get("reducer", "mean"),
                    custom_expression=self._params.get("custom_expression"),
                )
                self.series_ready.emit(job["label"], rows, job.get("color", ""))
            self.finished.emit()
        except Exception as e:
            error_message = f"Earth Engine Processing Error: {str(e)}"
            print(error_message)
            traceback.print_exc()
            self.failed.emit(error_message)
