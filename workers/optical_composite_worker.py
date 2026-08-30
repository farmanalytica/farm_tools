# -*- coding: utf-8 -*-
"""
Background worker for the synthetic index composite.

Builds and downloads a single-band vegetation-index composite reduced across
the user-selected dates (those still shown on the time-series plot) off the UI
thread. The AOI is extracted on the main thread and passed in.
"""

from dataclasses import dataclass, field
from typing import Optional

from qgis.PyQt.QtCore import pyqtSignal

from ..services.optical_service import OpticalService
from .background_worker import BackgroundWorker


@dataclass
class OpticalCompositeRequest:
    """Which dates to reduce, by which metric, and how to mask and write them."""

    aoi: object
    dates: list
    index_name: str
    metric: str
    buffer_m: float
    output_folder: Optional[str]
    apply_scl: bool = False
    invalid_scl_values: list = field(default_factory=list)
    custom_expression: Optional[str] = None


class OpticalCompositeWorker(BackgroundWorker):
    finished = pyqtSignal(str)   # output_path

    def __init__(self, request):
        super().__init__()
        self._request = request

    def work(self):
        request = self._request
        path = OpticalService.download_index_composite(
            request.aoi,
            request.dates,
            request.index_name,
            request.metric,
            apply_scl=request.apply_scl,
            invalid_scl_values=request.invalid_scl_values,
            buffer_m=request.buffer_m,
            output_folder=request.output_folder,
            custom_expression=request.custom_expression,
        )
        self.finished.emit(path)
