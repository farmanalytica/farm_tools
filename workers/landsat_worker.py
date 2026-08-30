from qgis.PyQt.QtCore import pyqtSignal

from ..services.landsat_service import LandsatService
from .background_worker import EarthEngineWorker


class LandsatWorker(EarthEngineWorker):
    """Discover available Landsat acquisition dates over the AOI/date-range,
    across all missions (Landsat 7/8/9)."""

    finished = pyqtSignal(object)  # list of (date, mission) tuples

    def __init__(self, aoi, params):
        super().__init__()
        self._aoi = aoi
        self._params = params

    def work(self):
        dated_missions = LandsatService.list_dated_missions(
            aoi=self._aoi,
            date_start=self._params.get("date_start"),
            date_end=self._params.get("date_end"),
            use_cloud_mask=self._params.get("use_cloud_mask", True),
            tier=self._params.get("tier", 1),
            min_valid_pct=self._params.get("min_valid_pct", 0),
            aoi_area_m2=self._params.get("aoi_area_m2"),
            missions=self._params.get("missions"),
        )
        self.finished.emit(dated_missions)
