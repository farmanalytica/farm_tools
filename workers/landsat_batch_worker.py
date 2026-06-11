# -*- coding: utf-8 -*-
"""
Background worker for the Landsat batch super-res download.

Pulls the pan-sharpened super-res RGB of every available ``(date, mission)`` in
parallel via a pure-asyncio fan-out (see
``LandsatService.download_superres_batch``), off the UI thread. Progress and
cancellation are bridged to Qt so a QProgressDialog can track and stop the run.
"""

import threading

from qgis.PyQt.QtCore import QThread, pyqtSignal

from ..services.landsat_service import LandsatService


class LandsatBatchWorker(QThread):
    progress = pyqtSignal(int, int)          # completed, total
    finished = pyqtSignal(int, int, list)    # successful, total, paths
    cancelled = pyqtSignal(int, int, list)   # successful, total, paths
    failed = pyqtSignal(str)

    def __init__(
        self, aoi, dated_missions, use_cloud_mask, tier, buffer_m, output_folder,
        min_valid_pct=0, aoi_area_m2=None,
    ):
        super().__init__()
        self._aoi = aoi
        self._pairs = list(dated_missions)
        self._use_cloud_mask = use_cloud_mask
        self._tier = tier
        self._buffer_m = buffer_m
        self._output_folder = output_folder
        self._min_valid_pct = min_valid_pct
        self._aoi_area_m2 = aoi_area_m2
        self._cancel = threading.Event()

    def request_cancel(self):
        self._cancel.set()

    def run(self):
        total = len(self._pairs)
        try:
            paths = LandsatService.download_superres_batch(
                self._aoi,
                self._pairs,
                use_cloud_mask=self._use_cloud_mask,
                tier=self._tier,
                buffer_m=self._buffer_m,
                output_folder=self._output_folder,
                progress_cb=lambda done, tot: self.progress.emit(done, tot),
                cancel_cb=self._cancel.is_set,
                min_valid_pct=self._min_valid_pct,
                aoi_area_m2=self._aoi_area_m2,
            )
        except Exception as e:
            self.failed.emit(str(e))
            return

        if self._cancel.is_set():
            self.cancelled.emit(len(paths), total, paths)
        else:
            self.finished.emit(len(paths), total, paths)
