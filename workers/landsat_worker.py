import traceback

from qgis.PyQt.QtCore import QThread, pyqtSignal

from ..services.landsat_service import LandsatService


class LandsatWorker(QThread):
    """Discover available Landsat acquisition dates over the AOI/date-range,
    across all missions (Landsat 7/8/9)."""

    finished = pyqtSignal(object)  # list of (date, mission) tuples
    failed = pyqtSignal(str)

    def __init__(self, aoi, params):
        super().__init__()
        self._aoi = aoi
        self._params = params

    def run(self):
        try:
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
        except Exception as e:
            error_message = f"Earth Engine Processing Error: {str(e)}"
            print(error_message)
            traceback.print_exc()
            self.failed.emit(error_message)
