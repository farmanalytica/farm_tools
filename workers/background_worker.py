# -*- coding: utf-8 -*-
"""
The shape every background job on this plugin shares.

Each page pushes its slow Earth Engine / network work onto a QThread and
reports failure to the UI rather than letting the thread die with a traceback
on stderr. ``BackgroundWorker`` owns that try/except so the workers themselves
contain only the work.
"""

import logging

from qgis.PyQt.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class BackgroundWorker(QThread):
    """A QThread whose ``work()`` failures arrive as a ``failed`` signal.

    Subclasses implement ``work()`` and declare their own success signals.
    Anything raised inside ``work()`` is logged and re-emitted as
    ``failed(message)``; override ``describe_failure`` to word that message
    for a particular page.
    """

    failed = pyqtSignal(str)

    def run(self):
        try:
            self.work()
        except Exception as exc:
            logger.exception("%s failed", type(self).__name__)
            self.failed.emit(self.describe_failure(exc))

    def work(self):
        """Do the job. Runs on the worker thread; must not touch Qt widgets."""
        raise NotImplementedError

    def describe_failure(self, exc):
        """The message sent with ``failed``."""
        return str(exc)


class EarthEngineWorker(BackgroundWorker):
    """A background worker whose failures are worth naming as Earth Engine's."""

    def describe_failure(self, exc):
        return f"Earth Engine Processing Error: {exc}"
