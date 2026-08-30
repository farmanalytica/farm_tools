# -*- coding: utf-8 -*-
"""
Background worker for single-date Landsat downloads (preview or export).

Downloads one scene for a date off the UI thread, in one of three kinds:
``"superres"`` (pan-sharpened 15 m RGB, TOA), ``"index"`` (single-band
vegetation index, 30 m SR) or ``"multispectral"`` (3-band RGB composite, 30 m
SR). The AOI is extracted on the main thread and passed in.
"""

from dataclasses import dataclass
from typing import Optional

from qgis.PyQt.QtCore import pyqtSignal

from ..services.landsat_service import LandsatService
from .background_worker import BackgroundWorker

KIND_SUPERRES = "superres"
KIND_INDEX = "index"
KIND_MULTISPECTRAL = "multispectral"


@dataclass
class LandsatPreviewRequest:
    """One Landsat scene to fetch: which date and mission, rendered how."""

    kind: str
    aoi: object
    date: str
    mission: str
    output_folder: Optional[str]
    buffer_m: float = 0
    index_name: str = ""
    mode: str = ""
    use_cloud_mask: bool = True
    tier: int = 1
    min_valid_pct: float = 0
    aoi_area_m2: Optional[float] = None


class LandsatPreviewWorker(BackgroundWorker):
    finished = pyqtSignal(str, str)   # output_path, kind

    def __init__(self, request):
        super().__init__()
        self._request = request

    def _common_options(self):
        request = self._request
        return {
            "use_cloud_mask": request.use_cloud_mask,
            "tier": request.tier,
            "buffer_m": request.buffer_m,
            "output_folder": request.output_folder,
            "min_valid_pct": request.min_valid_pct,
            "aoi_area_m2": request.aoi_area_m2,
        }

    def work(self):
        request = self._request
        options = self._common_options()

        if request.kind == KIND_SUPERRES:
            path = LandsatService.download_superres_for_date(
                request.aoi, request.date, request.mission, **options
            )
        elif request.kind == KIND_INDEX:
            path = LandsatService.download_index_for_date(
                request.aoi,
                request.date,
                request.mission,
                request.index_name,
                **options,
            )
        else:
            path = LandsatService.download_multispectral_for_date(
                request.aoi,
                request.date,
                request.mission,
                request.mode,
                **options,
            )
        self.finished.emit(path, request.kind)
