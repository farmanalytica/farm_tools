# -*- coding: utf-8 -*-
"""
Generic sequential batch-download worker.

Downloads one item per date off the UI thread, emitting progress so a
QProgressDialog can track it. The per-date work is injected as a
``download_one(date) -> path`` callable, so the same worker serves any page
(SAR, optical, …) without knowing the service details. The callable runs on
this thread and must not touch Qt widgets.
"""

from qgis.PyQt.QtCore import QThread, pyqtSignal, QMutex


class BatchDownloadWorker(QThread):
    progress = pyqtSignal(int, int, str)        # current, total, date
    finished = pyqtSignal(int, int, list)        # successful, total, paths
    cancelled = pyqtSignal(int, int, list)       # successful, total, paths
    failed = pyqtSignal(str)

    def __init__(self, dates, download_one):
        super().__init__()
        self._dates = list(dates)
        self._download_one = download_one
        self._cancel_requested = False
        self._mutex = QMutex()

    def request_cancel(self):
        self._mutex.lock()
        self._cancel_requested = True
        self._mutex.unlock()

    def _cancelled(self) -> bool:
        self._mutex.lock()
        flag = self._cancel_requested
        self._mutex.unlock()
        return flag

    def run(self):
        successful = 0
        total = len(self._dates)
        paths = []

        for index, date in enumerate(self._dates, start=1):
            if self._cancelled():
                self.cancelled.emit(successful, total, paths)
                return

            self.progress.emit(index, total, str(date))
            try:
                paths.append(self._download_one(date))
                successful += 1
            except Exception:
                pass

        self.finished.emit(successful, total, paths)
