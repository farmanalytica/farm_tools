# -*- coding: utf-8 -*-
"""Background worker for the ClimaPlots analysis pipeline.

Runs the climate-data fetch + climate-index computation off the GUI thread so
QGIS stays responsive. Uniform ``finished_ok`` / ``failed`` / ``progress``
signals, with the whole ``run`` body wrapped so any failure is surfaced to the
UI instead of crashing the thread.

The orchestrator import lives inside ``run()`` because it pulls extlibs
packages (climdex, pymannkendall, pyhomogeneity) that may not be provisioned
yet.
"""
import traceback

from qgis.PyQt.QtCore import QThread, pyqtSignal


class ClimaPlotsAnalysisWorker(QThread):
    """Fetch climate data and compute indices for one coordinate."""

    finished_ok = pyqtSignal(object)   # ClimateData
    failed = pyqtSignal(str)           # error message
    progress = pyqtSignal(str)         # human-readable status / per-index warning

    def __init__(self, longitude, latitude, proxy="", start_year=None, end_year=None,
                 longitude_b=None, latitude_b=None, source="power", source_b=None, parent=None):
        super().__init__(parent)
        self._longitude = longitude
        self._latitude = latitude
        self._proxy = proxy
        self._start_year = start_year
        self._end_year = end_year
        self._longitude_b = longitude_b
        self._latitude_b = latitude_b
        self._source = source
        self._source_b = source_b

    def run(self):
        try:
            from ..services.climaplots import orchestrator  # lazy: needs extlibs

            self.progress.emit("Fetching climate data...")
            data = orchestrator.run_analysis(
                self._longitude, self._latitude, self._proxy,
                warn=lambda msg: self.progress.emit(msg),
                start_year=self._start_year, end_year=self._end_year,
                longitude_b=self._longitude_b, latitude_b=self._latitude_b,
                source=self._source, source_b=self._source_b,
            )
            self.finished_ok.emit(data)
        except Exception:  # noqa: BLE001 - surface any failure to the UI
            self.failed.emit(traceback.format_exc())
