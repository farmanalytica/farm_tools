# -*- coding: utf-8 -*-
"""
Background worker for the SYSI page's GEE composite generation.

The GEOS3 pipeline (Sentinel-2 collection build, bare-soil masking, median
composite, and GeoTIFF download) is a slow network-bound operation that must
run off the UI thread to keep the dialog responsive.  The AOI is extracted
from the QGIS layer on the main thread (layers are not thread-safe) and
passed in already as an ee.FeatureCollection.
"""

from qgis.PyQt.QtCore import pyqtSignal

from ..services.sysi_service import SYSIService
from .background_worker import BackgroundWorker


_DEFAULT_LABEL = "Bare Soil"


class SYSIWorker(BackgroundWorker):
    """Run the GEOS3 bare-soil composite pipeline and download the result.

    Signals
    -------
    finished(output_path, label)
        Emitted on success with the local GeoTIFF path and a display label.
    failed(error_message)
        Emitted when any exception is raised during processing or download.
    """

    finished = pyqtSignal(str, str)

    def __init__(self, aoi, params):
        """
        Parameters
        ----------
        aoi : ee.FeatureCollection
            Area of interest, possibly buffered by the controller.
        params : dict
            Keys expected:
              start_date, end_date   – ``'YYYY-MM-DD'`` strings
              cloud_threshold        – int (0–100)
              ndvi_thres             – [min, max] floats
              nbr_thres              – [min, max] floats
              selected_months        – list[int] (1–12)
              output_folder          – str path (or None for system temp)
              label                  – str display name for the QGIS layer
        """
        super().__init__()
        self._aoi = aoi
        self._params = params

    def work(self):
        params = self._params
        composite = SYSIService.build_composite(
            aoi=self._aoi,
            start_date=params["start_date"],
            end_date=params["end_date"],
            cloud_threshold=params["cloud_threshold"],
            ndvi_thres=params["ndvi_thres"],
            nbr_thres=params["nbr_thres"],
            selected_months=params["selected_months"],
        )
        output_path = SYSIService.download_composite(
            composite,
            self._aoi,
            output_folder=params.get("output_folder"),
        )
        self.finished.emit(output_path, params.get("label", _DEFAULT_LABEL))
