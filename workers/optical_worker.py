import traceback

from qgis.PyQt.QtCore import QThread, pyqtSignal

from ..services.optical_service import OpticalService


class OpticalWorker(QThread):
    finished = pyqtSignal(object, str)
    failed = pyqtSignal(str)

    def __init__(self, aoi, params):
        super().__init__()
        self._aoi = aoi
        self._params = params

    def run(self):
        try:
            date_start = self._params.get("date_start")
            date_end = self._params.get("date_end")
            index_name = self._params.get("index_name", "NDVI")
            apply_scl = self._params.get("apply_scl", False)
            invalid_scl_values = self._params.get("invalid_scl_values", [])
            custom_expression = self._params.get("custom_expression", None)
            reducer = self._params.get("reducer", "mean")

            data_rows = OpticalService.get_time_series(
                aoi=self._aoi,
                date_start=date_start,
                date_end=date_end,
                index_name=index_name,
                apply_scl=apply_scl,
                invalid_scl_values=invalid_scl_values,
                custom_expression=custom_expression,
                reducer=reducer,
            )

            self.finished.emit(data_rows, index_name)

        except Exception as e:
            error_message = f"Earth Engine Processing Error: {str(e)}"
            print(error_message)
            traceback.print_exc()
            self.failed.emit(error_message)
