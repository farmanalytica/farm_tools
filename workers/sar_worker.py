# -*- coding: utf-8 -*-
"""
Background workers for the SAR page's network-bound operations.

The Earth Engine collection build, image download, and preview operations are
slow network calls, so they run off the UI thread to keep the dialog responsive.
The AOI is extracted from the QGIS layer on the main thread (layers are not
thread-safe) and passed in.
"""

from dataclasses import dataclass
from typing import Optional

from qgis.PyQt.QtCore import pyqtSignal

from ..services.sar_service import SARService
from .background_worker import BackgroundWorker

_DEFAULT_INDEX = "VV/VH Ratio"


class SARWorker(BackgroundWorker):
    """Runs the GEE collection build and spectral-index time-series fetch."""

    finished = pyqtSignal(object, object, str)

    def __init__(self, aoi, params):
        super().__init__()
        self._aoi = aoi
        self._params = params

    def work(self):
        parameters = self._params
        collection = SARService.get_collection(
            aoi=self._aoi,
            start_date=parameters["start_date"],
            end_date=parameters["end_date"],
            polarization=parameters["polarization"],
            output_format=parameters["output_format"],
            apply_border_noise_correction=parameters["border_noise"],
            apply_terrain_flattening=parameters["terrain"],
            apply_speckle_filtering=parameters["speckle"],
            ascending=False,
        )
        index_name = parameters.get("index", _DEFAULT_INDEX)
        meta = SARService.INDEX_REGISTRY[index_name]

        collection = collection.map(SARService.add_all_index_bands)
        data = SARService.get_index_timeseries(collection, self._aoi, meta["band"])
        self.finished.emit(collection, data, index_name)


@dataclass
class SarPreviewRequest:
    """The one dated scene to pull out of an already-built collection."""

    collection: object
    aoi: object
    selected_date: str
    output_folder: Optional[str]
    label: str


class SARPreviewWorker(BackgroundWorker):
    """Downloads a SAR image for preview or export off the UI thread."""

    finished = pyqtSignal(str, str)

    def __init__(self, request):
        super().__init__()
        self._request = request

    def work(self):
        request = self._request
        selected_image = SARService.get_dataset_image_for_date(
            request.collection,
            request.aoi,
            request.selected_date,
        )
        output_path = SARService.download_image(
            selected_image,
            request.aoi,
            request.selected_date,
            output_folder=request.output_folder,
        )
        self.finished.emit(output_path, request.label)


@dataclass
class SarCompositeRequest:
    """Which band, metric and dates the composite reduces, and what to call it."""

    collection: object
    aoi: object
    band_name: str
    index_label: str
    metric: str
    dates: list
    output_folder: Optional[str]
    label: str

    @property
    def start_date(self):
        """Earliest date in the reduction — the composite's nominal date."""
        return min(self.dates)


class SARCompositeWorker(BackgroundWorker):
    """Builds and downloads a single-index composite image off the UI thread."""

    finished = pyqtSignal(str, str)

    def __init__(self, request):
        super().__init__()
        self._request = request

    def work(self):
        request = self._request
        composite = SARService.build_band_composite(
            request.collection,
            request.aoi,
            request.band_name,
            request.metric,
            dates=request.dates,
            start_date=request.start_date,
        )
        output_path = SARService.download_band_composite(
            composite,
            request.aoi,
            request.metric,
            request.index_label,
            output_folder=request.output_folder,
        )
        self.finished.emit(output_path, request.label)
