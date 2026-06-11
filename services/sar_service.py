import os
import re
import tempfile

import ee
import requests
from ee_s1_ard import S1ARDImageCollection
from datetime import datetime, timedelta

try:
    from osgeo import gdal
except ImportError:
    gdal = None


class SARService:
    INDEX_REGISTRY = {
        "VV/VH Ratio": {
            "band": "VVVH_ratio",
            "add_fn": "add_vvvh_ratio_band",
            "title": "VV/VH Ratio Mean Time Series",
            "ylabel": "VV/VH Ratio Mean",
            "band_label": "VV/VH Ratio",
        },
        "RVI": {
            "band": "RVI",
            "add_fn": "add_rvi_band",
            "title": "Radar Vegetation Index (RVI) Time Series",
            "ylabel": "RVI Mean",
            "band_label": "RVI",
        },
        "DpRVI": {
            "band": "DpRVI",
            "add_fn": "add_dprvi_band",
            "title": "Dual-pol Vegetation Index (DpRVI) Time Series",
            "ylabel": "DpRVI Mean",
            "band_label": "DpRVI",
        },
        "Cross Ratio (VH/VV)": {
            "band": "CR",
            "add_fn": "add_cr_band",
            "title": "Cross Ratio (VH/VV) Time Series",
            "ylabel": "Cross Ratio Mean",
            "band_label": "CR",
        },
        "NDPI": {
            "band": "NDPI",
            "add_fn": "add_ndpi_band",
            "title": "Normalized Difference Polarization Index (NDPI) Time Series",
            "ylabel": "NDPI Mean",
            "band_label": "NDPI",
        },
        "Pol Difference (VV-VH)": {
            "band": "PD",
            "add_fn": "add_pd_band",
            "title": "Polarization Difference (VV-VH) Time Series",
            "ylabel": "Pol Difference Mean",
            "band_label": "PD",
        },
        "DPSVIm": {
            "band": "DPSVIm",
            "add_fn": "add_dpsvim_band",
            "title": "Modified Dual-pol SAR Vegetation Index (DPSVIm) Time Series",
            "ylabel": "DPSVIm Mean",
            "band_label": "DPSVIm",
        },
        "PRVI": {
            "band": "PRVI",
            "add_fn": "add_prvi_band",
            "title": "Polarimetric Radar Vegetation Index (PRVI) Time Series",
            "ylabel": "PRVI Mean",
            "band_label": "PRVI",
        },
        "mRVI": {
            "band": "mRVI",
            "add_fn": "add_mrvi_band",
            "title": "Modified Radar Vegetation Index (mRVI) Time Series",
            "ylabel": "mRVI Mean",
            "band_label": "mRVI",
        },
    }

    @staticmethod
    def get_collection(
        aoi,
        start_date,
        end_date,
        polarization,
        output_format,
        apply_border_noise_correction,
        apply_terrain_flattening,
        apply_speckle_filtering,
        ascending=False,
    ):
        processor = S1ARDImageCollection(
            geometry=aoi,
            start_date=start_date,
            stop_date=end_date,
            polarization=polarization,
            apply_border_noise_correction=apply_border_noise_correction,
            apply_terrain_flattening=apply_terrain_flattening,
            apply_speckle_filtering=apply_speckle_filtering,
            output_format=output_format,
            ascending=ascending,
        )

        return processor.get_collection().sort("system:time_start", False)

    @staticmethod
    def add_vvvh_ratio_band(image):
        ratio = image.select("VV").divide(image.select("VH")).rename("VVVH_ratio")
        return image.addBands(ratio)

    @staticmethod
    def add_rvi_band(image):
        rvi = (
            image.select("VH")
            .multiply(4)
            .divide(image.select("VV").add(image.select("VH")))
            .rename("RVI")
        )
        return image.addBands(rvi)

    @staticmethod
    def add_dprvi_band(image):
        dprvi = (
            image.select("VH")
            .divide(image.select("VH").add(image.select("VV")))
            .rename("DpRVI")
        )
        return image.addBands(dprvi)

    @staticmethod
    def add_cr_band(image):
        cr = image.select("VH").divide(image.select("VV")).rename("CR")
        return image.addBands(cr)

    @staticmethod
    def add_ndpi_band(image):
        vv = image.select("VV")
        vh = image.select("VH")
        ndpi = vv.subtract(vh).divide(vv.add(vh)).rename("NDPI")
        return image.addBands(ndpi)

    @staticmethod
    def add_pd_band(image):
        pd = image.select("VV").subtract(image.select("VH")).rename("PD")
        return image.addBands(pd)

    @staticmethod
    def add_dpsvim_band(image):
        vv = image.select("VV")
        vh = image.select("VH")
        dpsvim = vv.multiply(vv.add(vh)).divide(2 ** 0.5).rename("DPSVIm")
        return image.addBands(dpsvim)

    @staticmethod
    def add_prvi_band(image):
        vv = image.select("VV")
        vh = image.select("VH")
        prvi = vh.multiply(ee.Image(1).subtract(vh.divide(vv))).rename("PRVI")
        return image.addBands(prvi)

    @staticmethod
    def add_mrvi_band(image):
        vv = image.select("VV")
        vh = image.select("VH")
        denom = vv.add(vh)
        mrvi = (
            vv.divide(denom)
            .sqrt()
            .multiply(vh.multiply(4).divide(denom))
            .rename("mRVI")
        )
        return image.addBands(mrvi)

    @staticmethod
    def add_all_index_bands(image):
        image = SARService.add_vvvh_ratio_band(image)
        image = SARService.add_rvi_band(image)
        image = SARService.add_dprvi_band(image)
        image = SARService.add_cr_band(image)
        image = SARService.add_ndpi_band(image)
        image = SARService.add_pd_band(image)
        image = SARService.add_dpsvim_band(image)
        image = SARService.add_prvi_band(image)
        image = SARService.add_mrvi_band(image)
        return image

    @staticmethod
    def get_index_timeseries(collection, aoi, band_name):
        def get_mean(image):
            stats = image.select(band_name).reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=aoi,
                scale=10,
                maxPixels=1e9,
            )

            date = image.date().format("YYYY-MM-dd")

            return ee.Feature(
                None,
                {
                    "date": date,
                    f"{band_name}_mean": stats.get(band_name),
                },
            )

        result = collection.map(get_mean).getInfo()

        data = []
        for feature in result["features"]:
            properties = feature.get("properties", {})
            value = properties.get(f"{band_name}_mean")

            if value is None:
                continue
            data.append(
                {
                    "dates": properties.get("date"),
                    "AOI_average": value,
                }
            )

        return data

    COMPOSITE_METRICS = [
        "Mean",
        "Median",
        "Min",
        "Max",
        "Amplitude",
        "Standard Deviation",
        "Sum",
        "Area Under Curve (AUC)",
    ]

    @staticmethod
    def aggregate_index_collection(index_collection, metric, start_date=None):
        """Reduce a single-band index collection to one image by ``metric``."""
        first_image = index_collection.first()
        metric_functions = {
            "Mean": lambda: index_collection.mean(),
            "Median": lambda: index_collection.median(),
            "Min": lambda: index_collection.min(),
            "Max": lambda: index_collection.max(),
            "Amplitude": lambda: index_collection.max().subtract(
                index_collection.min()
            ),
            "Standard Deviation": lambda: index_collection.reduce(ee.Reducer.stdDev()),
            "Sum": lambda: index_collection.sum(),
            "Area Under Curve (AUC)": lambda: SARService._calculate_area_under_curve(
                index_collection, start_date
            ),
        }
        if metric not in metric_functions:
            raise ValueError(
                "Invalid metric: {}. Valid metrics: {}".format(
                    metric, ", ".join(metric_functions)
                )
            )
        result_image = metric_functions[metric]()

        return result_image.setDefaultProjection(first_image.projection())

    @staticmethod
    def _calculate_area_under_curve(index_collection, start_date):

        if start_date is None:
            raise ValueError("AUC requires a start date.")

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

        return first_image.select(0).multiply(0).add(auc_image)

    @staticmethod
    def build_band_composite(
        collection, aoi, band_name, metric, dates=None, start_date=None
    ):
        """Build a composite mosaic of unique band reduced by metric masked to the AOI"""
        date_collection = collection.map(
            lambda img: img.set("comp_date", img.date().format("YYYY-MM-dd"))
        )
        if dates:
            date_collection = date_collection.filter(
                ee.Filter.inList("comp_date", ee.List(list(dates)))
            )

        single_band_collection = date_collection.select(band_name)
        reduced_image = SARService.aggregate_index_collection(
            single_band_collection, metric, start_date
        )
        composite_image = reduced_image.rename(band_name).toFloat()

        geometry_mask = ee.Image(1).clip(aoi.geometry()).mask()
        return composite_image.updateMask(geometry_mask)

    @staticmethod
    def download_band_composite(image, aoi, metric, index_label, output_folder=None):

        download_url = image.getDownloadURL(
            {
                "scale": 10,
                "region": aoi.geometry().bounds().getInfo(),
                "format": "GeoTIFF",
                "crs": "EPSG:4326",
            }
        )
        response = requests.get(download_url, timeout=300)
        if not response.ok:
            raise RuntimeError(
                "SAR composite download failed (HTTP {}): {}".format(
                    response.status_code, response.reason
                )
            )

        def _sanitize(text):
            return re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_")

        filename = "SAR_{}_{}.tiff".format(_sanitize(index_label), _sanitize(metric))
        target_dir = (
            output_folder
            if (output_folder and os.path.isdir(output_folder))
            else tempfile.gettempdir()
        )
        output_path = SARService._get_unique_path(target_dir, filename)

        with open(output_path, "wb") as f:
            f.write(response.content)

        SARService._set_single_band_name(
            output_path, "{} {}".format(index_label, metric)
        )
        return output_path

    @staticmethod
    def _set_single_band_name(file_path, name):
        if gdal is None:
            return
        try:
            dataset = gdal.Open(file_path, gdal.GA_Update)
            if dataset is None:
                return
            band = dataset.GetRasterBand(1)
            if band is not None:
                band.SetDescription(name)
            dataset = None
        except Exception:
            pass

    @staticmethod
    def get_dataset_image_for_date(collection, aoi, date):
        next_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )

        return (
            collection.filterDate(date, next_date)
            .first()
            .select([
                "VV", "VH", "VVVH_ratio", "RVI", "DpRVI",
                "CR", "NDPI", "PD", "DPSVIm", "PRVI", "mRVI",
            ])
            .clip(aoi)
        )

    @staticmethod
    def download_image(
        image,
        aoi,
        date,
        output_folder=None,
    ):
        url = image.getDownloadURL(
            {
                "scale": 10,
                "region": aoi.geometry().bounds().getInfo(),
                "format": "GeoTIFF",
                "crs": "EPSG:4326",
            }
        )

        response = requests.get(url, timeout=300)
        if not response.ok:
            raise RuntimeError(
                f"SAR download failed (HTTP {response.status_code}): {response.reason}"
            )

        filename = f"Sentinel1_{date}.tiff"
        base_dir = (
            output_folder
            if (output_folder and os.path.isdir(output_folder))
            else tempfile.gettempdir()
        )
        output_path = SARService._get_unique_path(base_dir, filename)

        with open(output_path, "wb") as f:
            f.write(response.content)

        SARService._set_band_names(output_path)
        return output_path

    @staticmethod
    def _set_band_names(file_path):
        if gdal is None:
            return

        try:
            dataset = gdal.Open(file_path, gdal.GA_Update)
            if dataset is None:
                return

            band_names = [
                "VV", "VH", "VV/VH Ratio", "RVI", "DpRVI",
                "CR", "NDPI", "PD", "DPSVIm", "PRVI", "mRVI",
            ]
            for i in range(1, min(dataset.RasterCount + 1, len(band_names) + 1)):
                band = dataset.GetRasterBand(i)
                if band is not None:
                    band.SetDescription(band_names[i - 1])

            dataset = None
        except Exception:
            pass

    @staticmethod
    def _get_unique_path(folder, filename):
        candidate_path = os.path.join(folder, filename)
        if not os.path.exists(candidate_path):
            return candidate_path

        basename, extension = os.path.splitext(filename)
        counter = 1

        while True:
            candidate_path = os.path.join(folder, f"{basename}_{counter}{extension}")
            if not os.path.exists(candidate_path):
                return candidate_path
            counter += 1
