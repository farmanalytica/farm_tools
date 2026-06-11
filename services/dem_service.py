import os
import tempfile

import ee
import requests

from .dem_registry import DEMRegistry


class DEMService:
    """Service for downloading DEM data from Google Earth Engine."""

    @staticmethod
    def download_dem(aoi, dataset_name, output_folder=None):

        geometry = aoi.geometry()
        registry = DEMRegistry()
        raw_dem = registry.get_dataset_image(dataset_name).toFloat()

        geometry_mask = ee.Image(1).clip(geometry).mask()
        dem_image = raw_dem.updateMask(geometry_mask)

        download_url = dem_image.getDownloadURL(
            {"scale": 30, "region": geometry.bounds().getInfo(), "format": "GeoTIFF"}
        )

        response = requests.get(download_url, timeout=300)
        if not response.ok:
            raise RuntimeError(
                f"DEM download failed (HTTP {response.status_code}): {response.reason}"
            )

        safe_dataset_name = dataset_name.replace(" ", "_").replace("/", "-")
        filename = f"FARM_tools_{safe_dataset_name}.tif"

        target_dir = (
            output_folder
            if (output_folder and os.path.isdir(output_folder))
            else tempfile.gettempdir()
        )
        output_path = DEMService._get_unique_path(target_dir, filename)

        with open(output_path, "wb") as f:
            f.write(response.content)

        return output_path

    @staticmethod
    def _get_unique_path(folder: str, filename: str) -> str:

        candidate_path = os.path.join(folder, filename)
        if not os.path.exists(candidate_path):
            return candidate_path

        basename, extension = os.path.splitext(filename)
        counter = 1

        while True:
            candidate = os.path.join(folder, f"{basename}_{counter}{extension}")
            if not os.path.exists(candidate):
                return candidate
            counter += 1
