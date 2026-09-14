# -*- coding: utf-8 -*-
"""
Background worker for the Landsat index time series.

Builds, off the UI thread, the combined Landsat 7/8/9 time series for the
selected vegetation index using agrigee_lite's SITS engine, and returns it as a
pandas DataFrame. The AOI is passed as a shapely geometry (agrigee_lite's
``get.sits`` consumes shapely, not ee, geometries). The controller renders the
DataFrame with the shared plotly renderer (``view/sar_plot``).
"""

from dataclasses import dataclass
from typing import Optional

from qgis.PyQt.QtCore import pyqtSignal

from ..services.landsat_service import LandsatService
from .background_worker import BackgroundWorker


@dataclass
class LandsatTimeseriesRequest:
    """Which geometry, dates, index and quality filters the series covers."""

    shapely_geom: object
    date_start: str
    date_end: str
    index_name: str
    use_cloud_mask: bool = True
    tier: int = 1
    reducer: str = "mean"
    min_valid_pct: float = 0
    aoi_area_m2: Optional[float] = None
    missions: Optional[list] = None


class LandsatTimeseriesWorker(BackgroundWorker):
    finished = pyqtSignal(object, str)   # dataframe, index_name

    def __init__(self, request):
        super().__init__()
        self._request = request

    def work(self):
        request = self._request
        dataframe = LandsatService.get_index_timeseries_df(
            request.shapely_geom,
            request.date_start,
            request.date_end,
            request.index_name,
            use_cloud_mask=request.use_cloud_mask,
            tier=request.tier,
            reducer=request.reducer,
            min_valid_pct=request.min_valid_pct,
            aoi_area_m2=request.aoi_area_m2,
            missions=request.missions,
        )
        self.finished.emit(dataframe, request.index_name)
