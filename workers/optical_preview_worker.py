# -*- coding: utf-8 -*-
"""
Background worker for single-date optical downloads (preview or export).

Downloads one Sentinel-2 scene for a date off the UI thread: either the raw
multispectral stack (``kind="rgb"``) or a single-band vegetation index
(``kind="index"``). The AOI is extracted on the main thread and passed in.
"""

from qgis.PyQt.QtCore import QThread, pyqtSignal

from ..services.optical_service import OpticalService


class OpticalPreviewWorker(QThread):
    finished = pyqtSignal(str, str)   # output_path, kind
    failed = pyqtSignal(str)

    def __init__(
        self,
        kind,
        aoi,
        date,
        index_name,
        buffer_m,
        output_folder,
        custom_expression=None,
    ):
        super().__init__()
        self._kind = kind
        self._aoi = aoi
        self._date = date
        self._index_name = index_name
        self._buffer_m = buffer_m
        self._output_folder = output_folder
        self._custom_expression = custom_expression

    def run(self):
        try:
            if self._kind == "index":
                path = OpticalService.download_index_for_date(
                    self._aoi,
                    self._date,
                    self._index_name,
                    buffer_m=self._buffer_m,
                    output_folder=self._output_folder,
                    custom_expression=self._custom_expression,
                )
            else:
                path = OpticalService.download_multispectral_for_date(
                    self._aoi,
                    self._date,
                    buffer_m=self._buffer_m,
                    output_folder=self._output_folder,
                )
            self.finished.emit(path, self._kind)
        except Exception as e:
            self.failed.emit(str(e))
