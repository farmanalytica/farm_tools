# -*- coding: utf-8 -*-
"""
Dataset management module.

Handles dataset availability checking, registry queries, and UI updates
for available datasets in the selected AOI region.
"""

from qgis.PyQt.QtWidgets import QApplication

try:
    from qgis.PyQt.QtCore import Qt

    WAIT_CURSOR = Qt.CursorShape.WaitCursor
except AttributeError:
    from qgis.PyQt.QtCore import Qt

    WAIT_CURSOR = Qt.WaitCursor

from ..services.dem_registry import DEMRegistry


class DatasetManager:
    """Manages available datasets and dataset information display."""

    @staticmethod
    def load_available_datasets(
        dem_combo, current_aoi, current_aoi_bbox, on_error=None
    ):
        registry = DEMRegistry()
        dem_combo.clear()

        if not current_aoi:
            return

        QApplication.setOverrideCursor(WAIT_CURSOR)
        QApplication.processEvents()

        try:
            geometry = current_aoi.geometry()

            for dataset in registry.list_datasets():
                QApplication.processEvents()
                if registry.has_coverage(
                    dataset.name, geometry, aoi_bbox=current_aoi_bbox
                ):
                    dem_combo.addItem(dataset.name, dataset.name)
        except Exception as e:
            if on_error:
                on_error(str(e))
            else:
                raise
        finally:
            QApplication.restoreOverrideCursor()

    @staticmethod
    def update_dataset_info(dem_combo, dem_info_widget):

        dataset_name = dem_combo.currentData()
        if not dataset_name:
            dem_info_widget.clear()
            return

        registry = DEMRegistry()
        dataset = registry.get_dataset(dataset_name)
        dem_info_widget.setHtml(dataset.info)
