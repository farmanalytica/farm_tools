# -*- coding: utf-8 -*-
"""
Background worker for the NASA POWER climate overlay.

Resolves the AOI centroid and fetches daily climate data (precipitation +
min/max temperature) for the time-series date range off the UI thread. The AOI
(an Earth Engine FeatureCollection) is passed in; the centroid is resolved with
a getInfo call, which is why this must not run on the main thread.
"""

from qgis.PyQt.QtCore import pyqtSignal

from ..services.nasa_power_service import NasaPowerService
from .background_worker import BackgroundWorker

# The centroid only has to land inside the AOI to pick a POWER grid cell.
_CENTROID_MAX_ERROR_M = 1


class ClimateWorker(BackgroundWorker):
    finished = pyqtSignal(object)   # pandas.DataFrame

    def __init__(self, aoi, start_date, end_date, proxy=""):
        super().__init__()
        self._aoi = aoi
        self._start_date = start_date
        self._end_date = end_date
        self._proxy = proxy

    def work(self):
        coords = (
            self._aoi.geometry()
            .centroid(maxError=_CENTROID_MAX_ERROR_M)
            .coordinates()
            .getInfo()
        )
        longitude, latitude = coords[0], coords[1]
        daily = NasaPowerService.fetch_daily(
            longitude,
            latitude,
            self._start_date,
            self._end_date,
            proxy=self._proxy,
        )
        self.finished.emit(daily)
