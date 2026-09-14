# -*- coding: utf-8 -*-
"""
Basemap loading.

Adds the Google Hybrid XYZ basemap under the project's own layers, so a
freshly drawn or loaded AOI has imagery behind it.
"""

import logging

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import Qgis, QgsProject, QgsRasterLayer
from qgis.utils import iface

logger = logging.getLogger(__name__)

_LAYER_NAME = "Google Hybrid"
_XYZ_SOURCE = (
    "type=xyz&zmin=0&zmax=20&url="
    "https://mt1.google.com/vt/lyrs%3Dy%26x%3D{x}%26y%3D{y}%26z%3D{z}"
)
_XYZ_PROVIDER = "wms"
_BOTTOM_OF_LAYER_TREE = -1


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


def _add_layer():
    """Add the basemap under everything else. False when it was already there."""
    existing_names = [
        layer.name() for layer in QgsProject.instance().mapLayers().values()
    ]
    if _LAYER_NAME in existing_names:
        logger.debug("%s layer already added.", _LAYER_NAME)
        return False

    layer = QgsRasterLayer(_XYZ_SOURCE, _LAYER_NAME, _XYZ_PROVIDER)
    if not layer.isValid():
        logger.warning("Failed to load %s. Invalid layer.", _LAYER_NAME)
        return False

    QgsProject.instance().addMapLayer(layer, False)
    QgsProject.instance().layerTreeRoot().insertLayer(_BOTTOM_OF_LAYER_TREE, layer)
    iface.mapCanvas().refresh()
    return True


def load_google_hybrid_layer(interface):
    """Add the Google Hybrid basemap and confirm it on the message bar.

    Called from every page that offers a "load basemap" button. A basemap that
    fails to load is logged, not raised: it is a backdrop, not the task.
    """
    try:
        _add_layer()
    except Exception:
        logger.warning("Error loading %s", _LAYER_NAME, exc_info=True)
        return

    interface.messageBar().pushMessage(
        "FARM tools",
        _tr("Google Hybrid Layer loaded successfully"),
        level=Qgis.Success,
    )
