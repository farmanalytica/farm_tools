# -*- coding: utf-8 -*-
"""
SYSI (Synthetic Soil Image) service.

Implements the GEOS3 bare-soil composite pipeline for Sentinel-2 SR Harmonized
imagery.  The pipeline is a faithful port of the validated logic in
dev/08_sysi_soil_image.ipynb, with added empty-collection guards and
consistent download/naming helpers that follow the SAR service conventions.

GEOS3 bare-soil rule — a pixel is bare soil when ALL hold:
  • NDVI within [ndvi_min, ndvi_max]          (low vegetation)
  • NBR2 within [nbr_min, nbr_max]            (limits crop residue / NPV)
  • VNSIR ≤ 0.9                               (visible-to-SWIR slope for soil)
  • GRBL > 0  (Green > Blue)                  (rising visible slope)
  • REGR > 0  (Red   > Green)                 (continues the rising slope)
"""

import os
import tempfile

import ee
import requests

try:
    from osgeo import gdal
except ImportError:
    gdal = None


# --- Constants ---------------------------------------------------------------

# Raw Sentinel-2 band codes selected from S2_SR_HARMONIZED
_S2_BAND_NAMES = ['B2', 'B3', 'B4', 'B6', 'B8', 'B11', 'B12', 'QA60']

# Human-readable aliases (positional match with _S2_BAND_NAMES)
_FRIENDLY_NAMES = ['Blue', 'Green', 'Red', 'Rededge2', 'NIR', 'SWIR1', 'SWIR2', 'QA60']

# Bands rescaled to surface reflectance [0–1] (QA60 is kept for mask bookkeeping)
_OPTICAL_BANDS = ['Blue', 'Green', 'Red', 'Rededge2', 'NIR', 'SWIR1', 'SWIR2', 'QA60']

# Final export band order — matches the legacy bands_to_export list
_BANDS_TO_EXPORT = ['Blue', 'Green', 'Red', 'Rededge2', 'NIR', 'SWIR1', 'SWIR2', 'NDVI', 'NBR2']

# VNSIR threshold is fixed in the legacy implementation and not exposed to users
_VNSIR_THRESHOLD = 0.9


class SYSIService:
    """Service layer for the GEOS3 bare-soil composite pipeline."""

    # ------------------------------------------------------------------
    # Private image-level helpers (mapped over the collection)
    # ------------------------------------------------------------------

    @staticmethod
    def _mask_s2_clouds(image):
        """QA60 cloud / cirrus mask — bits 10 (clouds) and 11 (cirrus)."""
        qa = image.select('QA60')
        cloud_bit = 1 << 10
        cirrus_bit = 1 << 11
        mask = (
            qa.bitwiseAnd(cloud_bit).eq(0)
            .And(qa.bitwiseAnd(cirrus_bit).eq(0))
        )
        return image.updateMask(mask)

    @staticmethod
    def _add_indexes(image):
        """Compute NDVI, NBR2, GRBL, REGR from the renamed bands."""
        ndvi = image.normalizedDifference(['NIR', 'Red']).rename('NDVI')
        nbr2 = image.normalizedDifference(['SWIR1', 'SWIR2']).rename('NBR2')
        # GRBL/REGR are computed before scale-factor application; the > 0
        # condition is scale-invariant (Green > Blue ↔ GRBL > 0 at any scale).
        grbl = image.select('Green').subtract(image.select('Blue')).rename('GRBL')
        regr = image.select('Red').subtract(image.select('Green')).rename('REGR')
        return (
            image
            .addBands(ndvi)
            .addBands(nbr2)
            .addBands(grbl)
            .addBands(regr)
        )

    @staticmethod
    def _apply_scale_factors(image):
        """Divide optical + QA60 bands by 10 000 → surface reflectance [0–1]."""
        optical = image.select(_OPTICAL_BANDS).divide(10000)
        return image.addBands(optical, None, True)

    @staticmethod
    def _make_geos3_mapper(ndvi_thres, nbr_thres):
        """Return a closure that adds the GEOS3 mask band to an image."""
        def _add_geos3(image):
            # VNSIR = 1 − (2·Red − Green − Blue + 3·(NIR − Red))
            vnsir = ee.Image(1).subtract(
                ee.Image(2).multiply(image.select('Red'))
                .subtract(image.select('Green'))
                .subtract(image.select('Blue'))
                .add(
                    ee.Image(3).multiply(
                        image.select('NIR').subtract(image.select('Red'))
                    )
                )
            )
            geos3 = (
                image.select('NDVI').gte(ndvi_thres[0])
                .And(image.select('NDVI').lte(ndvi_thres[1]))
                .And(image.select('NBR2').gte(nbr_thres[0]))
                .And(image.select('NBR2').lte(nbr_thres[1]))
                .And(vnsir.lte(_VNSIR_THRESHOLD))
                .And(image.select('GRBL').gt(0))
                .And(image.select('REGR').gt(0))
            )
            return image.addBands(geos3.rename('GEOS3'))
        return _add_geos3

    @staticmethod
    def _mask_by_geos3(image):
        """Keep only pixels where GEOS3 == 1; also drop black-border no-data."""
        mask = (
            image.select('GEOS3').eq(1)
            .And(image.select('SWIR2').gte(0))
            .And(image.select('Green').gte(0))
            .And(image.select('Red').gte(0))
            .And(image.select('Blue').gte(0))
        )
        return image.updateMask(mask)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def build_composite(
        aoi,
        start_date,
        end_date,
        cloud_threshold,
        ndvi_thres,
        nbr_thres,
        selected_months,
    ):
        """Build a GEOS3 bare-soil composite ee.Image clipped to *aoi*.

        Parameters
        ----------
        aoi : ee.FeatureCollection
            Area of interest (may include a buffer applied by the controller).
        start_date, end_date : str  (``'YYYY-MM-DD'``)
        cloud_threshold : int
            Maximum ``CLOUDY_PIXEL_PERCENTAGE`` for a scene to be included.
        ndvi_thres : list[float, float]
            ``[min, max]`` NDVI range for bare-soil pixels.
        nbr_thres : list[float, float]
            ``[min, max]`` NBR2 range for bare-soil pixels.
        selected_months : list[int]
            Calendar months (1–12) to include.

        Returns
        -------
        ee.Image
            9-band float32 composite (Blue, Green, Red, Rededge2, NIR,
            SWIR1, SWIR2, NDVI, NBR2), clipped to *aoi*.

        Raises
        ------
        RuntimeError
            If the collection is empty after date/cloud or month filtering.
        """
        aoi_geometry = aoi.geometry()

        collection = (
            ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterDate(start_date, end_date)
            .filterBounds(aoi_geometry)
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', cloud_threshold))
            .map(SYSIService._mask_s2_clouds)
            .select(_S2_BAND_NAMES, _FRIENDLY_NAMES)
        )

        scene_count = collection.size().getInfo()
        if scene_count == 0:
            raise RuntimeError(
                "No Sentinel-2 scenes found for the given date range and cloud "
                "threshold. Try extending the date range or raising the cloud "
                "threshold."
            )

        def _tag_month(image):
            month = ee.Date(image.get('system:time_start')).get('month')
            return image.set('month', month)

        collection = (
            collection
            .map(_tag_month)
            .filter(ee.Filter.inList('month', ee.List(selected_months)))
        )

        scene_count_after_months = collection.size().getInfo()
        if scene_count_after_months == 0:
            raise RuntimeError(
                "No scenes found for the selected months. "
                "Try enabling more months or extending the date range."
            )

        geos3_mapper = SYSIService._make_geos3_mapper(ndvi_thres, nbr_thres)

        bare_soil_collection = (
            collection
            .map(SYSIService._add_indexes)
            .map(SYSIService._apply_scale_factors)
            .map(geos3_mapper)
            .map(SYSIService._mask_by_geos3)
        )

        composite = (
            bare_soil_collection
            .median()
            .select(_BANDS_TO_EXPORT)
            .toFloat()
            .clip(aoi_geometry)
        )

        return composite

    @staticmethod
    def download_composite(composite, aoi, output_folder=None):
        """Download *composite* as a GeoTIFF and return the local file path.

        Parameters
        ----------
        composite : ee.Image
            Output of :meth:`build_composite`.
        aoi : ee.FeatureCollection
            Used to derive the download bounding box.
        output_folder : str or None
            Target directory.  Falls back to the system temp directory if
            *output_folder* is ``None`` or does not exist.

        Returns
        -------
        str
            Absolute path to the downloaded GeoTIFF.
        """
        download_url = composite.getDownloadURL({
            'scale': 10,
            'region': aoi.geometry().bounds().getInfo(),
            'format': 'GeoTIFF',
            'crs': 'EPSG:4326',
        })

        response = requests.get(download_url, timeout=300)
        if not response.ok:
            raise RuntimeError(
                "SYSI download failed (HTTP {}): {}".format(
                    response.status_code, response.reason
                )
            )

        target_dir = (
            output_folder
            if (output_folder and os.path.isdir(output_folder))
            else tempfile.gettempdir()
        )
        output_path = SYSIService._get_unique_path(target_dir, "SYSI_composite.tiff")

        with open(output_path, "wb") as fh:
            fh.write(response.content)

        SYSIService._set_band_names(output_path)
        return output_path

    # ------------------------------------------------------------------
    # Private utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _set_band_names(file_path):
        """Write human-readable band descriptions into the GeoTIFF metadata."""
        if gdal is None:
            return
        try:
            dataset = gdal.Open(file_path, gdal.GA_Update)
            if dataset is None:
                return
            for i, name in enumerate(_BANDS_TO_EXPORT, start=1):
                if i <= dataset.RasterCount:
                    band = dataset.GetRasterBand(i)
                    if band is not None:
                        band.SetDescription(name)
            dataset = None
        except Exception:
            pass

    @staticmethod
    def _get_unique_path(folder, filename):
        candidate = os.path.join(folder, filename)
        if not os.path.exists(candidate):
            return candidate
        basename, ext = os.path.splitext(filename)
        counter = 1
        while True:
            candidate = os.path.join(folder, f"{basename}_{counter}{ext}")
            if not os.path.exists(candidate):
                return candidate
            counter += 1
