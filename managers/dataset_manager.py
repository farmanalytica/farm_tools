# -*- coding: utf-8 -*-
"""
Dataset management module.

Renders registry information for the DEM dataset selected on the DEM page.
"""

from ..services.dem_registry import DEMRegistry


class DatasetManager:
    """Manages available datasets and dataset information display."""

    @staticmethod
    def update_dataset_info(dem_combo, dem_info_widget) -> None:
        """Show the selected dataset's HTML blurb, or clear it when none is picked."""
        dataset_name = dem_combo.currentData()
        if not dataset_name:
            dem_info_widget.clear()
            return

        dataset = DEMRegistry().get_dataset(dataset_name)
        dem_info_widget.setHtml(dataset.info)
