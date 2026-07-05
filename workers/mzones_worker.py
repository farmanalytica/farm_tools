# -*- coding: utf-8 -*-
"""
Background workers for the Management Zones pipeline's heavy steps, so the
dialog stays responsive during resampling/extraction and the elbow +
silhouette analysis.
"""

from qgis.core import QgsProcessingFeedback
from qgis.PyQt.QtCore import QThread, pyqtSignal

from ..services.mzones import clustering_service, resampling_service
from ..services.mzones.resampling_service import OperationCancelled
from ..services.mzones.deps import DependencyMissing


class ElbowWorker(QThread):
    """Runs elbow + silhouette off the UI thread. cancel() interrupts
    between k fits."""

    progress = pyqtSignal(int, int)  # ks done, total
    finished = pyqtSignal(object)    # clustering_service.ElbowResult
    cancelled = pyqtSignal()
    dep_missing = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, dados, k_min, k_max):
        super().__init__()
        self._dados = dados
        self._k_min = k_min
        self._k_max = k_max

    def cancel(self):
        self.requestInterruption()

    def run(self):
        try:
            result = clustering_service.elbow_silhouette(
                self._dados, self._k_min, self._k_max,
                progress=self.progress.emit,
                should_stop=self.isInterruptionRequested,
            )
            if self.isInterruptionRequested():
                self.cancelled.emit()
                return
            self.finished.emit(result)
        except DependencyMissing as e:
            self.dep_missing.emit(e.user_message())
        except Exception as e:
            self.failed.emit(str(e))


class ResampleWorker(QThread):
    """Runs resample_and_extract off the UI thread.

    Processing algorithms are safe here because the service builds its own
    QgsProcessingContext; input layers are cloned in the constructor (on the
    UI thread) so project-owned layers never cross threads. cancel() cancels
    the shared feedback, aborting the running processing algorithm."""

    status = pyqtSignal(str, str, int)   # title, msg, level
    finished = pyqtSignal(object)        # resampling_service.ResampleResult
    cancelled = pyqtSignal()
    dep_missing = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, contorno_layer, rasters, resolucao):
        super().__init__()
        self._contorno = contorno_layer.clone()
        self._rasters = [r.clone() for r in rasters]
        self._resolucao = resolucao
        self._feedback = QgsProcessingFeedback()

    def cancel(self):
        self.requestInterruption()
        self._feedback.cancel()

    def run(self):
        try:
            result = resampling_service.resample_and_extract(
                self._contorno, self._rasters, self._resolucao,
                progress=self.status.emit,
                feedback=self._feedback,
            )
            if self._feedback.isCanceled():
                self.cancelled.emit()
                return
            self.finished.emit(result)
        except OperationCancelled:
            self.cancelled.emit()
        except DependencyMissing as e:
            self.dep_missing.emit(e.user_message())
        except Exception as e:
            # A cancelled feedback can surface as a processing exception —
            # report it as a cancellation, not an error.
            if self._feedback.isCanceled():
                self.cancelled.emit()
            else:
                self.failed.emit(str(e))
