# -*- coding: utf-8 -*-
"""
Background worker for the Landsat index time series.

Builds, off the UI thread, the combined Landsat 7/8/9 time series for the
selected vegetation index using agrigee_lite's SITS engine, and returns it as a
pandas DataFrame. The AOI is passed as a shapely geometry (agrigee_lite's
``get.sits`` consumes shapely, not ee, geometries). The controller renders the
DataFrame with the shared plotly renderer (``view/sar_plot``).
"""

from qgis.PyQt.QtCore import QThread, pyqtSignal

from ..services.landsat_service import LandsatService


class LandsatTimeseriesWorker(QThread):
    finished = pyqtSignal(object, str)   # dataframe, index_name
    failed = pyqtSignal(str)

    def __init__(
        self,
        shapely_geom,
        date_start,
        date_end,
        index_name,
        use_cloud_mask,
        tier,
        reducer,
        min_valid_pct=0,
        aoi_area_m2=None,
    ):
        super().__init__()
        self._geom = shapely_geom
        self._date_start = date_start
        self._date_end = date_end
        self._index_name = index_name
        self._use_cloud_mask = use_cloud_mask
        self._tier = tier
        self._reducer = reducer
        self._min_valid_pct = min_valid_pct
        self._aoi_area_m2 = aoi_area_m2

    def run(self):
        try:
            df = LandsatService.get_index_timeseries_df(
                self._geom,
                self._date_start,
                self._date_end,
                self._index_name,
                use_cloud_mask=self._use_cloud_mask,
                tier=self._tier,
                reducer=self._reducer,
                min_valid_pct=self._min_valid_pct,
                aoi_area_m2=self._aoi_area_m2,
            )
            self.finished.emit(df, self._index_name)
        except Exception as e:
            self.failed.emit(str(e))
