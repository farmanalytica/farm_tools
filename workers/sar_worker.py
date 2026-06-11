# -*- coding: utf-8 -*-
"""
Background workers for the SAR page's network-bound operations.

The Earth Engine collection build, image download, and preview operations are
slow network calls, so they run off the UI thread to keep the dialog responsive.
The AOI is extracted from the QGIS layer on the main thread (layers are not
thread-safe) and passed in.
"""

from qgis.PyQt.QtCore import QThread, pyqtSignal, QMutex

from ..services.sar_service import SARService


class SARWorker(QThread):
    """Runs the GEE collection build and spectral-index time-series fetch."""

    finished = pyqtSignal(object, object, str)
    failed = pyqtSignal(str)

    def __init__(self, aoi, params):
        super().__init__()
        self._aoi = aoi
        self._params = params

    def run(self):
        try:
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
            index_name = parameters.get("index", "VV/VH Ratio")
            meta = SARService.INDEX_REGISTRY[index_name]

            collection = collection.map(SARService.add_all_index_bands)

            data = SARService.get_index_timeseries(collection, self._aoi, meta["band"])
            self.finished.emit(collection, data, index_name)
        except Exception as e:
            self.failed.emit(str(e))


class SARPreviewWorker(QThread):
    """Downloads a SAR image for preview or export off the UI thread."""

    finished = pyqtSignal(str, str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        collection,
        aoi,
        selected_date,
        output_folder,
        label,
        index_band="VVVH_ratio",
        index_label="VV/VH Ratio",
    ):
        super().__init__()
        self._collection = collection
        self._aoi = aoi
        self._selected_date = selected_date
        self._output_folder = output_folder
        self._label = label
        self._index_band = index_band
        self._index_label = index_label

    def run(self):
        try:
            selected_image = SARService.get_dataset_image_for_date(
                self._collection,
                self._aoi,
                self._selected_date,
            )
            output_path = SARService.download_image(
                selected_image,
                self._aoi,
                self._selected_date,
                output_folder=self._output_folder,
            )
            self.finished.emit(output_path, self._label)
        except Exception as e:
            self.failed.emit(str(e))


class SARCompositeWorker(QThread):
    """Builds and downloads a single-index composite image off the UI thread."""

    finished = pyqtSignal(str, str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        collection,
        aoi,
        band_name,
        index_label,
        metric,
        dates,
        start_date,
        output_folder,
        label,
    ):
        super().__init__()
        self._collection = collection
        self._aoi = aoi
        self._band_name = band_name
        self._index_label = index_label
        self._metric = metric
        self._dates = dates
        self._start_date = start_date
        self._output_folder = output_folder
        self._label = label

    def run(self):
        try:
            composite = SARService.build_band_composite(
                self._collection,
                self._aoi,
                self._band_name,
                self._metric,
                dates=self._dates,
                start_date=self._start_date,
            )
            output_path = SARService.download_band_composite(
                composite,
                self._aoi,
                self._metric,
                self._index_label,
                output_folder=self._output_folder,
            )
            self.finished.emit(output_path, self._label)
        except Exception as e:
            self.failed.emit(str(e))


class SARBatchDownloadWorker(QThread):
    """Downloads multiple SAR images sequentially with progress tracking."""

    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int, int, list)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal(int, int, list)

    def __init__(
        self,
        collection,
        aoi,
        dates,
        output_folder,
        index_band="VVVH_ratio",
        index_label="VV/VH Ratio",
    ):
        super().__init__()
        self._collection = collection
        self._aoi = aoi
        self._dates = dates
        self._output_folder = output_folder
        self._index_band = index_band
        self._index_label = index_label
        self._cancel_requested = False
        self._mutex = QMutex()

    def request_cancel(self):
        self._mutex.lock()
        self._cancel_requested = True
        self._mutex.unlock()

    def run(self):
        successful = 0
        total = len(self._dates)
        downloaded_paths = []

        for index, date in enumerate(self._dates, start=1):
            self._mutex.lock()
            if self._cancel_requested:
                self._mutex.unlock()
                self.cancelled.emit(successful, total, downloaded_paths)
                return
            self._mutex.unlock()

            self.progress.emit(index, total, str(date))

            try:
                selected_image = SARService.get_dataset_image_for_date(
                    self._collection,
                    self._aoi,
                    date,
                )
                output_path = SARService.download_image(
                    selected_image,
                    self._aoi,
                    date,
                    output_folder=self._output_folder,
                )
                downloaded_paths.append(output_path)
                successful += 1
            except Exception:
                pass

        self.finished.emit(successful, total, downloaded_paths)
