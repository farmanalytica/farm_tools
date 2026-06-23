import os
import tempfile
from datetime import datetime, timedelta
from typing import List, Dict, Any

import ee
import requests

try:
    from osgeo import gdal
except ImportError:
    gdal = None

from ..tools.indexes import INDEX_REGISTRY, apply_custom


# Raw Sentinel-2 SR multispectral bands written by the batch download (no
# computed index bands). B10 is absent from the surface-reflectance product.
_MULTISPECTRAL_BANDS = [
    "B1",
    "B2",
    "B3",
    "B4",
    "B5",
    "B6",
    "B7",
    "B8",
    "B8A",
    "B9",
    "B11",
    "B12",
]


class OpticalService:
    """
    Service class responsible for interacting with Google Earth Engine to build
    Sentinel-2 time series data, compute vegetation indices, and extract image metadata.
    """

    @staticmethod
    def get_time_series(
        aoi: ee.FeatureCollection,
        date_start: str,
        date_end: str,
        index_name: str,
        apply_scl: bool,
        invalid_scl_values: List[int],
        custom_expression: str = None,
        reducer: str = "mean",
    ) -> List[Dict[str, Any]]:

        collection = OpticalService._build_base_collection(aoi, date_start, date_end)
        collection = OpticalService._keep_one_image_per_date(collection, aoi)

        def process_image(image):
            processed_image = OpticalService._add_vegetation_index(
                image, index_name, custom_expression
            )
            if apply_scl:
                processed_image = OpticalService._apply_scl_mask(
                    processed_image, invalid_scl_values
                )

            processed_image = OpticalService._calculate_image_metadata(
                processed_image, image.select("SCL"), aoi, invalid_scl_values, reducer
            )
            return processed_image

        processed_collection = collection.map(process_image).sort("system:time_start")

        return OpticalService._extract_data_rows(processed_collection)

    @staticmethod
    def _build_base_collection(
        aoi: ee.FeatureCollection, date_start: str, date_end: str
    ) -> ee.ImageCollection:
        return (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(aoi)
            .filterDate(date_start, date_end)
        )

    @staticmethod
    def _keep_one_image_per_date(
        collection: ee.ImageCollection, aoi: ee.FeatureCollection
    ) -> ee.ImageCollection:
        """Keep a single image per acquisition date (always on).

        Criteria: highest AOI footprint coverage first, cloud cover as the
        tiebreaker. Both come from cheap geometry/metadata (no reduceRegion), so
        the expensive per-image statistics are computed for the kept images
        alone -- unlike the legacy approach, which derived stats before
        deduplicating. Footprint coverage uses image.geometry() (the full MGRS
        tile for Sentinel-2), so single-tile AOIs tie at full coverage and the
        cloud tiebreaker decides.
        """
        geometry = aoi.geometry()
        aoi_area = geometry.area()

        def tag(image):
            coverage = (
                image.geometry()
                .intersection(geometry, ee.ErrorMargin(1))
                .area()
                .divide(aoi_area)
            )
            cloud = ee.Number(image.get("CLOUDY_PIXEL_PERCENTAGE"))
            # Composite descending score: coverage dominates, low cloud breaks
            # ties (coverage in [0,1] scaled by 1000 outweighs cloud in [0,100]).
            score = coverage.multiply(1000).subtract(cloud.divide(100))
            return image.set(
                {
                    "date": ee.Date(image.get("system:time_start")).format(
                        "YYYY-MM-dd"
                    ),
                    "dedup_score": score,
                }
            )

        # distinct() returns a generic Collection; re-cast to ImageCollection so
        # downstream map() yields ee.Image elements (not ee.Feature).
        deduped = collection.map(tag).sort("dedup_score", False).distinct("date")
        return ee.ImageCollection(deduped)

    @staticmethod
    def _build_valid_scl_mask(
        image: ee.Image, invalid_scl_values: List[int]
    ) -> ee.Image:

        scl = image.select("SCL")
        mask = ee.Image(1)
        for value in invalid_scl_values:
            mask = mask.And(scl.neq(value))
        return mask.rename("valid_scl")

    @staticmethod
    def _apply_scl_mask(image: ee.Image, invalid_scl_values: List[int]) -> ee.Image:
        return image.updateMask(
            OpticalService._build_valid_scl_mask(image, invalid_scl_values)
        )

    @staticmethod
    def _add_vegetation_index(
        image: ee.Image, index_name: str, custom_expression: str = None
    ) -> ee.Image:
        index_name_upper = index_name.upper()

        if custom_expression is not None:
            index_band = apply_custom(image, index_name, custom_expression).rename(
                "index"
            )

        elif index_name_upper in INDEX_REGISTRY:
            index_band = INDEX_REGISTRY[index_name_upper](image)

        else:
            raise ValueError(f"Index {index_name} is not recognized or implemented")

        return image.addBands(index_band)

    @staticmethod
    def _calculate_image_metadata(
        image: ee.Image,
        scl_band: ee.Image,
        aoi: ee.FeatureCollection,
        invalid_scl_values: List[int],
        reducer: str = "mean",
    ) -> ee.Image:

        geometry = aoi.geometry()

        # Geometry-based coverage (legacy): cheaper than a pixel count, but uses
        # image.geometry(), which for Sentinel-2 is the full nominal MGRS tile
        # square. AOIs inside a single tile therefore read ~100% even when the
        # swath only partially covers them; it only catches AOIs that extend
        # past a granule footprint (e.g. spanning multiple tiles).
        intersection_area = (
            image.geometry().intersection(geometry, ee.ErrorMargin(1)).area()
        )
        aoi_area = geometry.area()
        coverage_percentage = (
            ee.Number(intersection_area).divide(aoi_area).multiply(100)
        )

        total_pixels = (
            scl_band.unmask()
            .reduceRegion(
                reducer=ee.Reducer.count(), geometry=geometry, scale=10, maxPixels=1e9
            )
            .getNumber("SCL")
        )

        valid_mask = OpticalService._build_valid_scl_mask(
            image.addBands(scl_band, overwrite=True), invalid_scl_values
        )
        valid_pixels = (
            valid_mask.selfMask()
            .reduceRegion(
                reducer=ee.Reducer.count(), geometry=geometry, scale=10, maxPixels=1e9
            )
            .getNumber("valid_scl")
        )

        valid_pixel_percentage = ee.Algorithms.If(
            ee.Number(total_pixels).gt(0),
            ee.Number(valid_pixels).divide(total_pixels).multiply(100),
            0,
        )

        ee_reducer = ee.Reducer.median() if reducer == "median" else ee.Reducer.mean()
        aoi_dict = image.select("index").reduceRegion(
            reducer=ee_reducer,
            geometry=geometry,
            scale=10,
            maxPixels=1e9,
        )
        aoi_average = aoi_dict.get("index")

        return image.set(
            {
                "date": ee.Date(image.get("system:time_start")).format("YYYY-MM-dd"),
                "AOI_average": aoi_average,
                "cloud_pct": image.get("CLOUDY_PIXEL_PERCENTAGE"),
                "valid_pixel_pct": valid_pixel_percentage,
                "coverage_pct": coverage_percentage,
                "image_id": image.get("system:index"),
            }
        )

    @staticmethod
    def _extract_data_rows(collection: ee.ImageCollection) -> List[Dict[str, Any]]:

        def extract_properties(image):
            return ee.Feature(
                None,
                {
                    "date": image.get("date"),
                    "AOI_average": image.get("AOI_average"),
                    "cloud_pct": image.get("cloud_pct"),
                    "valid_pixel_pct": image.get("valid_pixel_pct"),
                    "coverage_pct": image.get("coverage_pct"),
                    "image_id": image.get("image_id"),
                },
            )

        feature_collection = ee.FeatureCollection(collection.map(extract_properties))
        info = feature_collection.getInfo()

        rows = []
        for feature in info.get("features", []):
            property = feature.get("properties", {})
            if property.get("AOI_average") is not None:
                rows.append(property)

        return rows

    # -- point / per-feature time series ----------------------------------
    @staticmethod
    def get_geometry_time_series(
        geometry: ee.Geometry,
        date_start: str,
        date_end: str,
        index_name: str,
        apply_scl: bool,
        invalid_scl_values: List[int],
        reducer: str = "mean",
        custom_expression: str = None,
    ) -> List[Dict[str, Any]]:
        """Vegetation-index time series for a single geometry over the full date
        range, returned as ``[{"date": str, "value": float}, ...]``.

        Mirrors the AOI series processing (one image per date, optional SCL
        masking) so the point/feature curves stay comparable to the AOI curve.

        ``reducer``:
          * ``"first"`` — exact value of the 10 m pixel containing the geometry
            (used for clicked points; truer than averaging a buffered disc).
          * ``"mean"``  — spatial mean over the geometry (used for polygon
            features).
        """
        collection = OpticalService._build_base_collection(geometry, date_start, date_end)
        # Keep one image per date by lowest cloud cover. The AOI-series
        # deduplicator divides by the AOI area (zero for a clicked point), so a
        # cloud-only rule is used here — correct for both points and polygons and
        # safe for degenerate geometries.
        def _tag_date(image):
            return image.set(
                "date",
                ee.Date(image.get("system:time_start")).format("YYYY-MM-dd"),
            )

        deduped = (
            collection.map(_tag_date)
            .sort("CLOUDY_PIXEL_PERCENTAGE")
            .distinct("date")
        )
        collection = ee.ImageCollection(deduped)

        ee_reducer = ee.Reducer.first() if reducer == "first" else ee.Reducer.mean()

        def process_image(image):
            img = OpticalService._add_vegetation_index(
                image, index_name, custom_expression
            )
            if apply_scl:
                img = OpticalService._apply_scl_mask(img, invalid_scl_values)
            value = img.select("index").reduceRegion(
                reducer=ee_reducer,
                geometry=geometry,
                scale=10,
                maxPixels=1e9,
            ).get("index")
            return image.set(
                {
                    "date": ee.Date(image.get("system:time_start")).format(
                        "YYYY-MM-dd"
                    ),
                    "value": value,
                }
            )

        processed = collection.map(process_image).filter(
            ee.Filter.notNull(["value"])
        )

        dates = processed.aggregate_array("date").getInfo()
        values = processed.aggregate_array("value").getInfo()

        rows = [
            {"date": d, "value": v}
            for d, v in zip(dates, values)
            if v is not None
        ]
        rows.sort(key=lambda r: r["date"])
        return rows

    # -- multispectral export (batch download) ----------------------------
    @staticmethod
    def _download_region(aoi: ee.FeatureCollection, buffer_m: float):
        """AOI geometry, optionally buffered (positive grows, negative crops)."""
        geometry = aoi.geometry()
        if buffer_m:
            geometry = geometry.buffer(buffer_m)
        return geometry

    @staticmethod
    def get_multispectral_image_for_date(
        aoi: ee.FeatureCollection, date: str, buffer_m: float = 0
    ):
        """Single Sentinel-2 SR multispectral image for ``date`` (one scene per
        date, same pick as the time series), clipped to the buffered AOI."""
        region = OpticalService._download_region(aoi, buffer_m)
        next_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )

        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(aoi)
            .filterDate(date, next_date)
        )
        collection = OpticalService._keep_one_image_per_date(collection, aoi)
        image = ee.Image(collection.first()).select(_MULTISPECTRAL_BANDS)
        return image.clip(region), region

    @staticmethod
    def download_multispectral_for_date(
        aoi: ee.FeatureCollection,
        date: str,
        buffer_m: float = 0,
        output_folder: str = None,
    ) -> str:
        """Download the multispectral scene for ``date`` as a GeoTIFF and return
        its path. Raises on a failed HTTP download."""
        image, region = OpticalService.get_multispectral_image_for_date(
            aoi, date, buffer_m
        )
        url = image.getDownloadURL(
            {
                "scale": 10,
                "region": region.bounds().getInfo(),
                "format": "GeoTIFF",
                "crs": "EPSG:4326",
            }
        )

        response = requests.get(url, timeout=300)
        if not response.ok:
            raise RuntimeError(
                f"Optical download failed (HTTP {response.status_code}): "
                f"{response.reason}"
            )

        base_dir = (
            output_folder
            if (output_folder and os.path.isdir(output_folder))
            else tempfile.gettempdir()
        )
        output_path = OpticalService._unique_path(base_dir, f"Sentinel2_{date}.tiff")
        with open(output_path, "wb") as f:
            f.write(response.content)

        OpticalService._set_band_names(output_path)
        return output_path

    @staticmethod
    def get_index_image_for_date(
        aoi: ee.FeatureCollection,
        date: str,
        index_name: str,
        buffer_m: float = 0,
        custom_expression: str = None,
    ):
        """Single-band vegetation-index image for ``date`` (same scene pick as
        the time series), clipped to the buffered AOI."""
        region = OpticalService._download_region(aoi, buffer_m)
        next_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )

        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(aoi)
            .filterDate(date, next_date)
        )
        collection = OpticalService._keep_one_image_per_date(collection, aoi)
        image = OpticalService._add_vegetation_index(
            ee.Image(collection.first()), index_name, custom_expression
        )
        return image.select("index").clip(region), region

    @staticmethod
    def download_index_for_date(
        aoi: ee.FeatureCollection,
        date: str,
        index_name: str,
        buffer_m: float = 0,
        output_folder: str = None,
        custom_expression: str = None,
    ) -> str:
        """Download the single-band index scene for ``date`` as a GeoTIFF."""
        image, region = OpticalService.get_index_image_for_date(
            aoi, date, index_name, buffer_m, custom_expression
        )
        url = image.getDownloadURL(
            {
                "scale": 10,
                "region": region.bounds().getInfo(),
                "format": "GeoTIFF",
                "crs": "EPSG:4326",
            }
        )

        response = requests.get(url, timeout=300)
        if not response.ok:
            raise RuntimeError(
                f"Optical download failed (HTTP {response.status_code}): "
                f"{response.reason}"
            )

        base_dir = (
            output_folder
            if (output_folder and os.path.isdir(output_folder))
            else tempfile.gettempdir()
        )
        output_path = OpticalService._unique_path(
            base_dir, f"S2_{index_name}_{date}.tiff"
        )
        with open(output_path, "wb") as f:
            f.write(response.content)
        return output_path

    # -- synthetic index composite (selected dates) -----------------------
    @staticmethod
    def build_index_composite(
        aoi: ee.FeatureCollection,
        dates: List[str],
        index_name: str,
        metric: str,
        apply_scl: bool = False,
        invalid_scl_values: List[int] = None,
        buffer_m: float = 0,
        custom_expression: str = None,
    ):
        """Aggregate the vegetation index across only the given acquisition
        dates (those still shown on the plot) into a single composite image.

        Mirrors the time-series processing (same one-scene-per-date pick and SCL
        masking) so the composite reflects the values the user sees, then reduces
        the per-date index stack with ``metric``. Returns ``(image, region)``.
        """
        if not dates:
            raise ValueError("No dates selected for the composite.")
        invalid_scl_values = invalid_scl_values or []
        sorted_dates = sorted(dates)
        start = sorted_dates[0]
        end = (
            datetime.strptime(sorted_dates[-1], "%Y-%m-%d") + timedelta(days=1)
        ).strftime("%Y-%m-%d")
        region = OpticalService._download_region(aoi, buffer_m)

        collection = OpticalService._build_base_collection(aoi, start, end)
        collection = OpticalService._keep_one_image_per_date(collection, aoi)
        # Keep only the user-selected dates (those left on the plot).
        collection = collection.filter(
            ee.Filter.inList("date", ee.List(sorted_dates))
        )

        def add_index(image):
            img = image
            if apply_scl:
                img = OpticalService._apply_scl_mask(img, invalid_scl_values)
            index_band = OpticalService._add_vegetation_index(
                img, index_name, custom_expression
            ).select("index")
            return index_band.copyProperties(image, ["system:time_start"])

        index_collection = ee.ImageCollection(collection.map(add_index))

        if metric == "Area Under Curve (AUC)":
            first_image = index_collection.first()
            result_image = OpticalService._calculate_auc(index_collection, start)
            result_image = result_image.setDefaultProjection(
                first_image.projection()
            ).clip(first_image.geometry())
        else:
            result_image = OpticalService._aggregate_index_collection(
                index_collection, metric
            )

        # Cast to float so NoData is representable, then clip to the exact AOI
        # via an explicit mask (the GeoTIFF region stays a rectangle).
        final_image = result_image.toFloat()
        mask = ee.Image(1).clip(aoi.geometry()).mask()
        final_image = final_image.updateMask(mask).clip(region)
        return final_image.rename("index"), region

    @staticmethod
    def _aggregate_index_collection(index_collection: ee.ImageCollection, metric: str):
        """Reduce a per-date index collection to one image by ``metric``.

        The result is re-aligned to the first image's projection
        (``setDefaultProjection``) and clipped to its geometry so the composite
        keeps a consistent spatial grid — without this the reducer output has a
        default 1-degree projection and downloads misaligned/blank.
        """
        first_image = index_collection.first()
        metric_functions = {
            "Mean": lambda: index_collection.mean(),
            "Median": lambda: index_collection.median(),
            "Min": lambda: index_collection.min(),
            "Max": lambda: index_collection.max(),
            "Amplitude": lambda: index_collection.max().subtract(
                index_collection.min()
            ),
            "Standard Deviation": lambda: index_collection.reduce(
                ee.Reducer.stdDev()
            ).rename("index"),
            "Sum": lambda: index_collection.sum(),
        }
        if metric not in metric_functions:
            valid = ", ".join(list(metric_functions.keys()) + ["Area Under Curve (AUC)"])
            raise ValueError(f"Invalid metric: {metric}. Valid metrics are: {valid}")

        result_image = metric_functions[metric]()
        aligned_image = result_image.setDefaultProjection(
            first_image.projection()
        ).clip(first_image.geometry())
        return aligned_image

    @staticmethod
    def _calculate_auc(index_collection: ee.ImageCollection, start_date: str):
        """Area-under-curve of the index over time (trapezoidal rule), with the
        first image's footprint and projection preserved."""
        first_image = index_collection.first()
        index_stack = index_collection.toBands()
        valid_mask = index_stack.mask().reduce(ee.Reducer.min())

        start = ee.Date(start_date)
        timestamps = index_collection.aggregate_array("system:time_start").map(
            lambda d: ee.Date(d).difference(start, "day")
        )
        time_diffs = (
            ee.List(timestamps)
            .slice(0, -1)
            .zip(ee.List(timestamps).slice(1))
            .map(
                lambda pair: ee.Number(ee.List(pair).get(1)).subtract(
                    ee.Number(ee.List(pair).get(0))
                )
            )
        )
        index_array = index_stack.toArray()
        sums = index_array.arraySlice(0, 1).add(index_array.arraySlice(0, 0, -1))
        auc = (
            ee.Image.constant(time_diffs)
            .toArray()
            .multiply(sums)
            .divide(2)
            .arrayReduce(ee.Reducer.sum(), [0])
        )
        auc_image = auc.arrayGet([0]).updateMask(valid_mask)
        # Re-anchor to the first image's footprint (legacy behaviour).
        final_image = first_image.select(0).multiply(0).add(auc_image)
        return final_image

    @staticmethod
    def download_index_composite(
        aoi: ee.FeatureCollection,
        dates: List[str],
        index_name: str,
        metric: str,
        apply_scl: bool = False,
        invalid_scl_values: List[int] = None,
        buffer_m: float = 0,
        output_folder: str = None,
        custom_expression: str = None,
    ) -> str:
        """Build the composite and download it as a GeoTIFF; return its path."""
        image, region = OpticalService.build_index_composite(
            aoi,
            dates,
            index_name,
            metric,
            apply_scl=apply_scl,
            invalid_scl_values=invalid_scl_values,
            buffer_m=buffer_m,
            custom_expression=custom_expression,
        )
        url = image.getDownloadURL(
            {
                "scale": 10,
                "region": region.bounds().getInfo(),
                "format": "GeoTIFF",
                "crs": "EPSG:4326",
            }
        )

        response = requests.get(url, timeout=300)
        if not response.ok:
            raise RuntimeError(
                f"Composite download failed (HTTP {response.status_code}): "
                f"{response.reason}"
            )

        base_dir = (
            output_folder
            if (output_folder and os.path.isdir(output_folder))
            else tempfile.gettempdir()
        )
        safe_metric = (
            metric.replace(" ", "_").replace("(", "").replace(")", "")
        )
        output_path = OpticalService._unique_path(
            base_dir, f"S2_{index_name}_{safe_metric}.tiff"
        )
        with open(output_path, "wb") as f:
            f.write(response.content)
        return output_path

    @staticmethod
    def _unique_path(folder: str, filename: str) -> str:
        path = os.path.join(folder, filename)
        if not os.path.exists(path):
            return path
        stem, ext = os.path.splitext(filename)
        i = 1
        while os.path.exists(os.path.join(folder, f"{stem}_{i}{ext}")):
            i += 1
        return os.path.join(folder, f"{stem}_{i}{ext}")

    @staticmethod
    def _set_band_names(file_path: str):
        if gdal is None:
            return
        try:
            dataset = gdal.Open(file_path, gdal.GA_Update)
            if dataset is None:
                return
            for i in range(
                1, min(dataset.RasterCount + 1, len(_MULTISPECTRAL_BANDS) + 1)
            ):
                band = dataset.GetRasterBand(i)
                if band is not None:
                    band.SetDescription(_MULTISPECTRAL_BANDS[i - 1])
            dataset = None
        except Exception:
            pass
