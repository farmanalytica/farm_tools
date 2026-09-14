# -*- coding: utf-8 -*-
"""
Background worker for the MapBiomas page.

Rendering the MapBiomas previews is a slow, network-bound Earth Engine job (one
``getThumbURL`` per coverage year, plus the transition thumbnail and its
histogram) that must run off the UI thread. The AOI is extracted from the QGIS
layer on the main thread (layers are not thread-safe) and passed in as an
``ee.FeatureCollection``.

One worker serves every MapBiomas product; ``MapBiomasRequest.mode`` picks
which, and the result dict carries the same mode back so the controller knows
what it received.
"""

from dataclasses import dataclass
from typing import Optional

from qgis.PyQt.QtCore import pyqtSignal

from ..services.mapbiomas_service import MapBiomasService
from .background_worker import BackgroundWorker

MODE_COVERAGE = "coverage"
MODE_DOWNLOAD = "download"
MODE_DOWNLOAD_TRANSITION = "download_transition"
MODE_TRANSITION_MAP = "transition_map"
MODE_TRANSITION = "transition"


@dataclass
class MapBiomasRequest:
    """Which MapBiomas product to build, and the inputs that product needs.

    ``output_dir`` is the scratch folder for rendered thumbnails;
    ``output_folder`` is the user's download folder for GeoTIFFs.
    """

    aoi: object
    mode: str
    output_dir: Optional[str] = None
    output_folder: Optional[str] = None
    year: Optional[int] = None
    source_classes: Optional[list] = None
    target_classes: Optional[list] = None
    year_min: Optional[int] = None
    year_max: Optional[int] = None


class MapBiomasWorker(BackgroundWorker):
    """Render MapBiomas previews (coverage years or transition) off the UI thread.

    Signals
    -------
    finished(result)
        Emitted on success with a dict whose ``"mode"`` names the product, e.g.
        ``{"mode": "coverage", "images": {year: path}}`` or
        ``{"mode": "download", "path": str, "year": int}``.
    failed(error_message)
        Emitted when any exception is raised during processing.
    progress(message, done, total)
        Emitted as each year / stage completes.
    """

    finished = pyqtSignal(object)
    progress = pyqtSignal(str, int, int)

    def __init__(self, request):
        super().__init__()
        self._request = request
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def work(self):
        handlers = {
            MODE_COVERAGE: self._render_coverage,
            MODE_DOWNLOAD: self._download_year,
            MODE_DOWNLOAD_TRANSITION: self._download_transition,
            MODE_TRANSITION_MAP: self._render_transition_map,
        }
        handler = handlers.get(self._request.mode, self._render_transition)
        result = handler()
        if result is not None:
            self.finished.emit(result)

    def _render_coverage(self):
        images = MapBiomasService.download_coverage_thumbnails(
            self._request.aoi,
            self._request.output_dir,
            progress_cb=self._emit_progress,
            cancel_cb=lambda: self._cancelled,
        )
        if self._cancelled:
            return None
        return {"mode": MODE_COVERAGE, "images": images}

    def _download_year(self):
        path = MapBiomasService.download_coverage_geotiff(
            self._request.aoi,
            self._request.year,
            output_folder=self._request.output_folder,
        )
        return {"mode": MODE_DOWNLOAD, "path": path, "year": self._request.year}

    def _download_transition(self):
        request = self._request
        path = MapBiomasService.download_transition_geotiff(
            request.aoi,
            request.source_classes,
            request.target_classes,
            output_folder=request.output_folder,
            year_min=request.year_min,
            year_max=request.year_max,
        )
        return {"mode": MODE_DOWNLOAD_TRANSITION, "path": path}

    def _render_transition_map(self):
        request = self._request
        path = MapBiomasService.render_transition_map(
            request.aoi,
            request.output_dir,
            request.source_classes,
            request.target_classes,
            year_min=request.year_min,
            year_max=request.year_max,
            progress_cb=self._emit_progress,
        )
        return {"mode": MODE_TRANSITION_MAP, "image": path}

    def _render_transition(self):
        request = self._request
        path, stats = MapBiomasService.download_transition(
            request.aoi,
            request.output_dir,
            request.source_classes,
            request.target_classes,
            progress_cb=self._emit_progress,
        )
        return {"mode": MODE_TRANSITION, "image": path, "stats": stats}

    def _emit_progress(self, message, done, total):
        self.progress.emit(message, done, total)
