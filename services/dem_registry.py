import ee
import json
from pathlib import Path


def get_ee_bbox(aoi):
    """
    Extract the bounding box of an EE object, returning the  EE
    Geometry and the local coords [min_x, min_y, max_x, max_y]
    """
    if isinstance(aoi, ee.Geometry):
        geometry = aoi
    else:
        geometry = aoi.geometry()

    bounds_info = geometry.bounds().getInfo()
    coords = bounds_info["coordinates"][0]

    xs = [p[0] for p in coords]
    ys = [p[1] for p in coords]

    return geometry, (min(xs), min(ys), max(xs), max(ys))


def check_bbox_intersects(a, b):

    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


class DEMDataset:
    """Represents a single DEM dataset entry from the catalog."""

    def __init__(self, **kwargs):
        self.name = kwargs["name"]
        self.collection = kwargs["collection"]
        self.band = kwargs["band"]
        self.resolution = kwargs["resolution"]
        self.description = kwargs["description"]
        self.is_global = kwargs["is_global"]
        self.is_collection = kwargs["is_collection"]
        self.coverage_bbox = kwargs.get("coverage_bbox")
        self.info = kwargs["info"]

    def get_dataset_image(self) -> ee.Image:
        """Returns mosaicked ee.Image from the collection, or a single ee.Image"""
        if self.is_collection:
            return ee.ImageCollection(self.collection).select(self.band).mosaic()

        return ee.Image(self.collection).select(self.band)


class DEMRegistry:
    """
    Registry of available DEM datasets loaded from the catalog JSON.

    Provides lookup and availability-check operations against Google Earth Engine.
    """

    def __init__(self):
        catalog_path = Path(__file__).parent.parent / "assets" / "dem_catalog.json"

        with open(catalog_path, encoding="utf-8-sig") as f:
            data = json.load(f)

        self._datasets = {d["name"]: DEMDataset(**d) for d in data}

    def list_datasets(self):

        return list(self._datasets.values())

    def get_dataset(self, name: str) -> DEMDataset:

        if name not in self._datasets:
            raise ValueError(f"Dataset '{name}' not found.")
        return self._datasets[name]

    def get_dataset_image(self, name: str) -> ee.Image:

        return self.get_dataset(name).get_dataset_image()

    def has_coverage(self, name: str, region, aoi_bbox=None) -> bool:
        """Check if the dataset has coverage over the given region in Earth Engine."""

        dataset = self.get_dataset(name)

        if aoi_bbox is None:
            geometry, aoi_bbox = get_ee_bbox(region)
        else:
            geometry = region if isinstance(region, ee.Geometry) else region.geometry()

        if dataset.coverage_bbox:
            if not check_bbox_intersects(dataset.coverage_bbox, aoi_bbox):
                return False

        try:
            if dataset.is_collection:
                return (
                    ee.ImageCollection(dataset.collection)
                    .filterBounds(geometry)
                    .size()
                    .getInfo()
                    > 0
                )

            else:
                image = ee.Image(dataset.collection)

                reduced = image.reduceRegion(
                    reducer=ee.Reducer.count(),
                    geometry=geometry,
                    scale=1000,
                    maxPixels=1e6,
                )

                band_value = reduced.get(dataset.band)
                return band_value.getInfo() > 0 if band_value else False

        except Exception:
            return False
