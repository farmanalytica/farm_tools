# -*- coding: utf-8 -*-
"""Capture canvas snapshots for PDF embedding."""

import os
import tempfile

from qgis.PyQt.QtCore import QCoreApplication


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


def capture_canvas_snapshot(canvas, max_width=None):
    """Capture current canvas view to a temporary PNG path."""
    temp = tempfile.NamedTemporaryFile(
        prefix="farm_tools_fieldguide_canvas_", suffix=".png", delete=False
    )
    temp_path = temp.name
    temp.close()

    # Use QGIS native export to capture the full map extent
    canvas.saveAsImage(temp_path, None, "PNG")

    # Check if file was created successfully
    if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
        raise RuntimeError(_tr("Could not capture the current map image."))

    return temp_path
