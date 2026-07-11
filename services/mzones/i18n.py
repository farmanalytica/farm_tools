# -*- coding: utf-8 -*-
"""Translation shim so code copied from precision_zones keeps calling tr()
while resolving through farm_tools' single translation context."""
from qgis.PyQt.QtCore import QCoreApplication


def tr(text: str) -> str:
    return QCoreApplication.translate("RAVI", text)
