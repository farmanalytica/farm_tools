# -*- coding: utf-8 -*-
"""
Background worker for the NASA POWER climate overlay.

Resolves the AOI centroid and fetches daily climate data (precipitation +
min/max temperature) for the time-series date range off the UI thread. The AOI
(an Earth Engine FeatureCollection) is passed in; the centroid is resolved with
a getInfo call, which is why this must not run on the main thread.
"""

from qgis.PyQt.QtCore import QThread, pyqtSignal

from ..services.nasa_power_service import NasaPowerService


class ClimateWorker(QThread):
    finished = pyqtSignal(object)   # pandas.DataFrame
    failed = pyqtSignal(str)

    def __init__(self, aoi, start_date, end_date, proxy=""):
        super().__init__()
        self._aoi = aoi
        self._start_date = start_date
        self._end_date = end_date
        self._proxy = proxy

    def run(self):
        try:
            coords = (
                self._aoi.geometry()
                .centroid(maxError=1)
                .coordinates()
                .getInfo()
            )
            longitude, latitude = coords[0], coords[1]
            df = NasaPowerService.fetch_daily(
                longitude,
                latitude,
                self._start_date,
                self._end_date,
                proxy=self._proxy,
            )
            self.finished.emit(df)
        except Exception as e:
            self.failed.emit(str(e))
