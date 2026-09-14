# -*- coding: utf-8 -*-
"""Background worker for the ClimaPlots analysis pipeline.

Runs the climate-data fetch + climate-index computation off the GUI thread so
QGIS stays responsive, with the whole run wrapped so any failure is surfaced to
the UI instead of crashing the thread.

The orchestrator import lives inside ``work()`` because it pulls extlibs
packages (climdex, pymannkendall, pyhomogeneity) that may not be provisioned
yet.
"""

import traceback
from dataclasses import dataclass
from typing import Optional

from qgis.PyQt.QtCore import pyqtSignal

from .background_worker import BackgroundWorker

DEFAULT_SOURCE = "power"


@dataclass
class ClimaPlotsRequest:
    """One analysis run: a primary coordinate, an optional comparison, a period."""

    longitude: str
    latitude: str
    proxy: str = ""
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    longitude_b: Optional[str] = None
    latitude_b: Optional[str] = None
    source: str = DEFAULT_SOURCE
    source_b: Optional[str] = None


class ClimaPlotsAnalysisWorker(BackgroundWorker):
    """Fetch climate data and compute indices for one coordinate."""

    finished_ok = pyqtSignal(object)   # ClimateData
    progress = pyqtSignal(str)         # human-readable status / per-index warning

    def __init__(self, request, parent=None):
        super().__init__(parent)
        self._request = request

    def work(self):
        from ..services.climaplots import orchestrator  # lazy: needs extlibs

        request = self._request
        self.progress.emit("Fetching climate data...")
        data = orchestrator.run_analysis(
            request.longitude,
            request.latitude,
            request.proxy,
            warn=self.progress.emit,
            start_year=request.start_year,
            end_year=request.end_year,
            longitude_b=request.longitude_b,
            latitude_b=request.latitude_b,
            source=request.source,
            source_b=request.source_b,
        )
        self.finished_ok.emit(data)

    def describe_failure(self, exc):
        """The UI shows the whole traceback: these failures are usually in extlibs."""
        return traceback.format_exc()
