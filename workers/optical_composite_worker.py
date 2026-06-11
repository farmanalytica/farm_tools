# -*- coding: utf-8 -*-
"""
Background worker for the synthetic index composite.

Builds and downloads a single-band vegetation-index composite reduced across
the user-selected dates (those still shown on the time-series plot) off the UI
thread. The AOI is extracted on the main thread and passed in.
"""

from qgis.PyQt.QtCore import QThread, pyqtSignal

from ..services.optical_service import OpticalService


class OpticalCompositeWorker(QThread):
    finished = pyqtSignal(str)   # output_path
    failed = pyqtSignal(str)

    def __init__(
        self,
        aoi,
        dates,
        index_name,
        metric,
        apply_scl,
        invalid_scl_values,
        buffer_m,
        output_folder,
        custom_expression=None,
    ):
        super().__init__()
        self._aoi = aoi
        self._dates = dates
        self._index_name = index_name
        self._metric = metric
        self._apply_scl = apply_scl
        self._invalid_scl_values = invalid_scl_values
        self._buffer_m = buffer_m
        self._output_folder = output_folder
        self._custom_expression = custom_expression

    def run(self):
        try:
            path = OpticalService.download_index_composite(
                self._aoi,
                self._dates,
                self._index_name,
                self._metric,
                apply_scl=self._apply_scl,
                invalid_scl_values=self._invalid_scl_values,
                buffer_m=self._buffer_m,
                output_folder=self._output_folder,
                custom_expression=self._custom_expression,
            )
            self.finished.emit(path)
        except Exception as e:
            self.failed.emit(str(e))
