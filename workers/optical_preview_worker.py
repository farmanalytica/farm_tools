# -*- coding: utf-8 -*-
"""
Background worker for single-date optical downloads (preview or export).

Downloads one Sentinel-2 scene for a date off the UI thread: either the raw
multispectral stack (``kind="rgb"``) or a single-band vegetation index
(``kind="index"``). The AOI is extracted on the main thread and passed in.
"""

from dataclasses import dataclass
from typing import Optional

from qgis.PyQt.QtCore import pyqtSignal

from ..services.optical_service import OpticalService
from .background_worker import BackgroundWorker

KIND_INDEX = "index"
KIND_RGB = "rgb"


@dataclass
class OpticalPreviewRequest:
    """One scene to fetch: which date, rendered how, written where."""

    kind: str
    aoi: object
    date: str
    index_name: str
    buffer_m: float
    output_folder: Optional[str]
    custom_expression: Optional[str] = None


class OpticalPreviewWorker(BackgroundWorker):
    finished = pyqtSignal(str, str)   # output_path, kind

    def __init__(self, request):
        super().__init__()
        self._request = request

    def work(self):
        request = self._request
        if request.kind == KIND_INDEX:
            path = OpticalService.download_index_for_date(
                request.aoi,
                request.date,
                request.index_name,
                buffer_m=request.buffer_m,
                output_folder=request.output_folder,
                custom_expression=request.custom_expression,
            )
        else:
            path = OpticalService.download_multispectral_for_date(
                request.aoi,
                request.date,
                buffer_m=request.buffer_m,
                output_folder=request.output_folder,
            )
        self.finished.emit(path, request.kind)
