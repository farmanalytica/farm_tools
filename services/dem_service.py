
import ee

from .dem_registry import DEMRegistry
from .downloads import DEM_SCALE_M, GeoTiffRequest, download_geotiff


class DEMService:
    """Service for downloading DEM data from Google Earth Engine."""

    @staticmethod
    def download_dem(aoi, dataset_name, output_folder=None):

        geometry = aoi.geometry()
        registry = DEMRegistry()
        raw_dem = registry.get_dataset_image(dataset_name).toFloat()

        geometry_mask = ee.Image(1).clip(geometry).mask()
        dem_image = raw_dem.updateMask(geometry_mask)

        safe_dataset_name = dataset_name.replace(" ", "_").replace("/", "-")
        return download_geotiff(
            dem_image,
            GeoTiffRequest(
                region=geometry,
                filename=f"FARM_tools_{safe_dataset_name}.tif",
                output_folder=output_folder,
                scale=DEM_SCALE_M,
                product="DEM",
                crs=None,
            ),
        )

