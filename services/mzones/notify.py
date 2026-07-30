# -*- coding: utf-8 -*-
"""Notifier: thin wrapper over the QGIS message bar and QMessageBox.

Replaces the ~30 inline `try/except: iface.messageBar().pushMessage(...)` blocks
and the scattered QMessageBox calls. `status()` never raises.
"""
import logging

from qgis.PyQt.QtWidgets import QMessageBox

logger = logging.getLogger(__name__)


class Notifier:
    # message bar levels (Qgis.MessageLevel): Info=0, Warning=1, Critical=2
    INFO = 0
    WARNING = 1
    CRITICAL = 2

    def __init__(self, iface=None):
        self.iface = iface

    def status(self, title: str, msg: str, level: int = INFO):
        """Non-blocking message bar notice. Swallows all exceptions."""
        try:
            self.iface.messageBar().pushMessage(title, msg, level=level)
        except Exception:
            logger.debug("Failed to push message bar notice (title=%s)", title, exc_info=True)

    def info(self, parent, title: str, msg: str):
        QMessageBox.information(parent, title, msg)

    def warning(self, parent, title: str, msg: str):
        QMessageBox.warning(parent, title, msg)

    def critical(self, parent, title: str, msg: str):
        QMessageBox.critical(parent, title, msg)
