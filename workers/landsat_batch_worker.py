# -*- coding: utf-8 -*-
"""
Background worker for the Landsat batch super-res download.

Pulls the pan-sharpened super-res RGB of every available ``(date, mission)`` in
parallel via a pure-asyncio fan-out (see
``LandsatService.download_superres_batch``), off the UI thread. Progress and
cancellation are bridged to Qt so a QProgressDialog can track and stop the run.
"""

import threading
from dataclasses import dataclass
from typing import Optional

from qgis.PyQt.QtCore import pyqtSignal

from ..services.landsat_service import LandsatService
from .background_worker import BackgroundWorker


@dataclass
class LandsatBatchRequest:
    """Every ``(date, mission)`` to fetch, and the quality filters to fetch it under."""

    aoi: object
    dated_missions: list
    output_folder: Optional[str]
    buffer_m: float = 0
    use_cloud_mask: bool = True
    tier: int = 1
    min_valid_pct: float = 0
    aoi_area_m2: Optional[float] = None


class LandsatBatchWorker(BackgroundWorker):
    progress = pyqtSignal(int, int)          # completed, total
    finished = pyqtSignal(int, int, list)    # successful, total, paths
    cancelled = pyqtSignal(int, int, list)   # successful, total, paths

    def __init__(self, request):
        super().__init__()
        self._request = request
        self._pairs = list(request.dated_missions)
        self._cancel = threading.Event()

    def request_cancel(self):
        self._cancel.set()

    def work(self):
        request = self._request
        paths = LandsatService.download_superres_batch(
            request.aoi,
            self._pairs,
            use_cloud_mask=request.use_cloud_mask,
            tier=request.tier,
            buffer_m=request.buffer_m,
            output_folder=request.output_folder,
            progress_cb=self.progress.emit,
            cancel_cb=self._cancel.is_set,
            min_valid_pct=request.min_valid_pct,
            aoi_area_m2=request.aoi_area_m2,
        )

        total = len(self._pairs)
        if self._cancel.is_set():
            self.cancelled.emit(len(paths), total, paths)
        else:
            self.finished.emit(len(paths), total, paths)
