# -*- coding: utf-8 -*-
"""
Background worker for the MapBiomas page.

Rendering the MapBiomas previews is a slow, network-bound Earth Engine job (one
``getThumbURL`` per coverage year, plus the transition thumbnail and its
histogram) that must run off the UI thread. The AOI is extracted from the QGIS
layer on the main thread (layers are not thread-safe) and passed in as an
``ee.FeatureCollection``.

A single worker handles both products via *mode*; the result is delivered as a
plain dict so the controller can branch on ``mode``.
"""

from qgis.PyQt.QtCore import QThread, pyqtSignal

from ..services.mapbiomas_service import MapBiomasService


class MapBiomasWorker(QThread):
    """Render MapBiomas previews (coverage years or transition) off the UI thread.

    Signals
    -------
    finished(result)
        Emitted on success with a dict:
          ``{"mode": "coverage", "images": {year: path}}``,
          ``{"mode": "transition", "image": path, "stats": dict}`` or
          ``{"mode": "download", "path": str, "year": int}``.
    failed(error_message)
        Emitted when any exception is raised during processing.
    progress(message, done, total)
        Emitted as each year / stage completes.
    """

    finished = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(str, int, int)

    def __init__(self, aoi, mode, output_dir=None, year=None, output_folder=None,
                 source_classes=None, target_classes=None,
                 year_min=None, year_max=None):
        super().__init__()
        self._aoi = aoi
        self._mode = mode
        self._output_dir = output_dir
        self._year = year
        self._output_folder = output_folder
        self._source_classes = source_classes
        self._target_classes = target_classes
        self._year_min = year_min
        self._year_max = year_max
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            if self._mode == "coverage":
                images = MapBiomasService.download_coverage_thumbnails(
                    self._aoi,
                    self._output_dir,
                    progress_cb=self._emit_progress,
                    cancel_cb=lambda: self._cancelled,
                )
                if self._cancelled:
                    return
                self.finished.emit({"mode": "coverage", "images": images})
            elif self._mode == "download":
                path = MapBiomasService.download_coverage_geotiff(
                    self._aoi, self._year, output_folder=self._output_folder
                )
                self.finished.emit(
                    {"mode": "download", "path": path, "year": self._year}
                )
            elif self._mode == "download_transition":
                path = MapBiomasService.download_transition_geotiff(
                    self._aoi, self._source_classes, self._target_classes,
                    output_folder=self._output_folder,
                    year_min=self._year_min, year_max=self._year_max,
                )
                self.finished.emit({"mode": "download_transition", "path": path})
            elif self._mode == "transition_map":
                path = MapBiomasService.render_transition_map(
                    self._aoi, self._output_dir,
                    self._source_classes, self._target_classes,
                    year_min=self._year_min, year_max=self._year_max,
                    progress_cb=self._emit_progress,
                )
                self.finished.emit({"mode": "transition_map", "image": path})
            else:
                path, stats = MapBiomasService.download_transition(
                    self._aoi, self._output_dir,
                    self._source_classes, self._target_classes,
                    progress_cb=self._emit_progress,
                )
                self.finished.emit(
                    {"mode": "transition", "image": path, "stats": stats}
                )
        except Exception as exc:
            self.failed.emit(str(exc))

    def _emit_progress(self, message, done, total):
        self.progress.emit(message, done, total)
