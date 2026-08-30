# -*- coding: utf-8 -*-
"""Resampling + extraction service: warp/clip rasters to a snapped grid, sample
pixel centroids into a points DataFrame. Pure backend (no QMessageBox)."""
import logging
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Optional

import numpy as np
from osgeo import gdal

from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsCoordinateTransform,
)
from qgis import processing

from .deps import import_pandas
from .i18n import tr
from .raster_io import compute_grid, estimate_utm_crs
from .data_cleaning import limpar_dataframe

logger = logging.getLogger(__name__)


class OperationCancelled(Exception):
    """Raised when the caller's feedback requested cancellation."""


@dataclass
class ResampleResult:
    df: Any                              # cleaned points DataFrame (may be empty)
    ref_gt: tuple
    ref_crs_wkt: str
    grid_shape: tuple
    referencia_raster: Any               # QgsRasterLayer
    matriz_variaveis_originais: Any      # ndarray
    colunas_variaveis_originais: list
    n_removed: int
    zero_var_cols: list
    target_crs_authid: str               # working CRS (auto-UTM if input was geographic)
    reprojected: bool = False            # True when a geographic boundary was auto-reprojected to UTM


# QGIS processing exposes GDAL's resampling algorithms as an enum index.
_RESAMPLE_NEAREST = 0
_RESAMPLE_BILINEAR = 1
# gdal:warpreproject's DATA_TYPE 0 means "same as input".
_DATA_TYPE_AS_INPUT = 0
_FIRST_BAND = 1
_TEMP_NAME_HEX_CHARS = 8
# Columns that describe where a sample is, not what was measured there.
_NON_VARIABLE_COLUMNS = ("X", "Y", "valor")


@dataclass
class _Steps:
    """The three side-channels each step needs: run, report, bail out."""

    run: Callable
    say: Callable
    check_cancel: Callable


@dataclass
class _TargetGrid:
    """The snapped, metric grid every raster is warped and clipped onto."""

    crs: Any
    resolution: float
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    @classmethod
    def from_boundary(cls, boundary, resolution):
        extent = boundary.extent()
        return cls(
            crs=boundary.crs(),
            resolution=resolution,
            x_min=extent.xMinimum(),
            x_max=extent.xMaximum(),
            y_min=extent.yMinimum(),
            y_max=extent.yMaximum(),
        )

    @property
    def authid(self):
        return self.crs.authid()

    @property
    def extent_str(self):
        return f"{self.x_min},{self.x_max},{self.y_min},{self.y_max}"

    @property
    def width_px(self):
        return max(1, int(np.ceil((self.x_max - self.x_min) / self.resolution)))

    @property
    def height_px(self):
        return max(1, int(np.ceil((self.y_max - self.y_min) / self.resolution)))

    def intersects(self, extent):
        return (
            extent.xMaximum() > self.x_min and extent.xMinimum() < self.x_max
            and extent.yMaximum() > self.y_min and extent.yMinimum() < self.y_max
        )


def _reproject_boundary_to_utm(boundary, context, feedback):
    """The boundary in its appropriate UTM CRS, so metric resolution means something.

    Silent by design: the conversion is an implementation detail the user never
    acts on.
    """
    reprojected = processing.run("native:reprojectlayer", {
        "INPUT": boundary,
        "TARGET_CRS": estimate_utm_crs(boundary),
        "OUTPUT": "memory:boundary_utm",
    }, context=context, feedback=feedback).get("OUTPUT")

    if isinstance(reprojected, str):
        reprojected = QgsVectorLayer(reprojected, "boundary_utm", "ogr")
    if reprojected is None or not reprojected.isValid():
        raise Exception(tr("Failed to reproject boundary to UTM."))
    return reprojected


def _warp_via_processing(raster, grid, warp_path, run):
    """Warp with QGIS processing. Returns the produced path, or ``None``."""
    try:
        result = run("gdal:warpreproject", {
            "INPUT": raster.source(),
            "SOURCE_CRS": raster.crs().authid(),
            "TARGET_CRS": grid.authid,
            "RESAMPLING": _RESAMPLE_BILINEAR,
            "NODATA": None,
            "TARGET_RESOLUTION": [grid.resolution, grid.resolution],
            "TARGET_EXTENT": grid.extent_str,
            "TARGET_EXTENT_CRS": grid.authid,
            "MULTITHREADING": True,
            "DATA_TYPE": _DATA_TYPE_AS_INPUT,
            "EXTRA": f"-tap -ts {grid.width_px} {grid.height_px}",
            "OUTPUT": warp_path,
        })
    except Exception:
        logger.debug("gdal:warpreproject failed for %s", raster.name(), exc_info=True)
        return None

    produced = result.get("OUTPUT", warp_path)
    if not produced or not os.path.exists(produced):
        return None
    if os.path.normpath(produced) != os.path.normpath(warp_path):
        try:
            shutil.copyfile(produced, warp_path)
        except Exception:
            logger.debug(
                "Failed to copy warped output %s to %s", produced, warp_path,
                exc_info=True,
            )
            return None
    return warp_path


def _warp_via_gdal(raster, grid, warp_path):
    """Fall back to calling GDAL directly when the processing algorithm balks."""
    try:
        gdal.Warp(
            destNameOrDestDS=warp_path,
            srcDSOrSrcDSTab=raster.source(),
            format="GTiff",
            dstSRS=grid.authid,
            xRes=grid.resolution,
            yRes=grid.resolution,
            outputBounds=(grid.x_min, grid.y_min, grid.x_max, grid.y_max),
            resampleAlg=gdal.GRA_Bilinear,
            warpOptions=["MULTITHREAD=YES", "TARGET_ALIGNED_PIXELS=TRUE"],
            creationOptions=["COMPRESS=LZW", "TILED=YES"],
        )
    except Exception:
        logger.debug("gdal.Warp failed for %s", raster.name(), exc_info=True)
        return None
    return warp_path if os.path.exists(warp_path) else None


def _points_to_dataframe(points_layer, pd):
    """Every fully-populated single-part point as an ``{X, Y, **fields}`` row."""
    field_names = [field.name() for field in points_layer.fields()]
    rows = []
    for feature in points_layer.getFeatures():
        attributes = feature.attributes()
        if None in attributes:
            continue
        geometry = feature.geometry()
        if not geometry or geometry.isMultipart():
            continue
        point = geometry.asPoint()
        row = {"X": point.x(), "Y": point.y()}
        row.update(dict(zip(field_names, attributes)))
        rows.append(row)
    return pd.DataFrame(rows)


def _variable_matrix(df):
    """The measured variables as a matrix, dropping the coordinate columns."""
    if df is None or df.empty:
        return None, []
    numeric = df.select_dtypes(include=[np.number]).copy()
    dropped = [col for col in _NON_VARIABLE_COLUMNS if col in numeric.columns]
    if dropped:
        numeric = numeric.drop(columns=dropped)
    return numeric.values, numeric.columns.tolist()


def _grid_metadata(reference_raster, fallback):
    """``(geotransform, crs_wkt, shape)`` read back from the written raster.

    Falls back to the caller's values when the file cannot be reopened.
    """
    try:
        path = reference_raster.dataProvider().dataSourceUri().split("|")[0]
        dataset = gdal.Open(path)
        if dataset:
            return (
                dataset.GetGeoTransform(),
                dataset.GetProjection(),
                (dataset.RasterYSize, dataset.RasterXSize),
            )
    except Exception:
        logger.debug(
            "Failed to read grid metadata (geotransform/CRS/shape) from the "
            "reference output raster; keeping previous defaults", exc_info=True,
        )
    return fallback


def resample_and_extract(contorno_layer, rasters, resolucao: float,
                         progress: Optional[Callable] = None,
                         feedback=None) -> ResampleResult:
    """Warp/resample + clip each raster to the boundary grid, then sample
    pixel-centroid points across all rasters into a DataFrame.

    `progress(title, msg, level)` is an optional status sink. `feedback` is an
    optional QgsProcessingFeedback; cancelling it aborts the running
    processing algorithm and raises OperationCancelled at the next check.
    Raises Exception(translated) on hard failures.
    """
    pd = import_pandas()

    context = QgsProcessingContext()
    context.setTransformContext(QgsProject.instance().transformContext())
    if feedback is None:
        feedback = QgsProcessingFeedback()

    def say(title, message, level=0):
        if progress:
            progress(title, message, level)

    def run(algorithm, parameters):
        return processing.run(
            algorithm, parameters, context=context, feedback=feedback
        )

    def check_cancel():
        if feedback.isCanceled():
            raise OperationCancelled()

    steps = _Steps(run=run, say=say, check_cancel=check_cancel)

    boundary = contorno_layer
    reprojected = boundary.crs().isGeographic()
    if reprojected:
        boundary = _reproject_boundary_to_utm(boundary, context, feedback)

    if hasattr(boundary, "updateExtents"):
        boundary.updateExtents()

    grid = _TargetGrid.from_boundary(boundary, resolucao)
    ref_gt, (rows, cols) = compute_grid(boundary.extent(), resolucao)
    grid_metadata = (ref_gt, boundary.crs().toWkt(), (rows, cols))

    clipped = _RasterResampler(boundary, grid, steps).resample_all(rasters)

    check_cancel()
    say(tr("Processing"), tr("Generating centroid points..."))
    points_layer = _pixel_centroids(clipped[0], run)
    points_layer = _sample_rasters(points_layer, clipped, steps)

    check_cancel()
    df = _points_to_dataframe(points_layer, pd)
    df, n_removed, zero_var_cols = limpar_dataframe(df, pd)
    matrix, columns = _variable_matrix(df)

    ref_gt, ref_crs_wkt, grid_shape = _grid_metadata(clipped[0], grid_metadata)

    return ResampleResult(
        df=df, ref_gt=ref_gt, ref_crs_wkt=ref_crs_wkt, grid_shape=grid_shape,
        referencia_raster=clipped[0],
        matriz_variaveis_originais=matrix, colunas_variaveis_originais=columns,
        n_removed=n_removed, zero_var_cols=zero_var_cols,
        target_crs_authid=grid.authid, reprojected=reprojected,
    )


class _RasterResampler:
    """Warps and clips each input raster onto one snapped grid.

    Holds the boundary, the grid and the three side-channels every step needs
    (run an algorithm, report progress, bail out on cancel) so the steps
    themselves stay small.
    """

    def __init__(self, boundary, grid, steps):
        self._boundary = boundary
        self._grid = grid
        self._steps = steps
        self._scratch_dir = tempfile.mkdtemp(prefix="pz_warp_")

    def resample_all(self, rasters):
        """Every raster that reaches the grid, warped and clipped onto it."""
        clipped = [self._resample_one(raster) for raster in rasters]
        clipped = [layer for layer in clipped if layer is not None]
        if not clipped:
            raise Exception(tr("Resampling failed."))
        return clipped

    def _resample_one(self, raster):
        steps = self._steps
        steps.check_cancel()
        steps.say(tr("Processing"),
                  tr("Reprojecting/resampling {}...").format(raster.name()))

        if not self._overlaps_grid(raster):
            steps.say(tr("Warning"),
                      tr("{}: raster does not intersect boundary after "
                         "reprojection — skipping.").format(raster.name()),
                      level=1)
            return None

        warped = self._warp(raster)
        steps.check_cancel()
        if warped is None:
            raise Exception(tr("Warp produced no output."))

        steps.say(tr("Processing"),
                  tr("Clipping {} by boundary...").format(raster.name()))
        return self._clip(warped, raster.name())

    def _overlaps_grid(self, raster):
        """True when ``raster`` reaches the grid — or when the check itself fails."""
        try:
            transform = QgsCoordinateTransform(
                raster.crs(), self._grid.crs, QgsProject.instance().transformContext()
            )
            return self._grid.intersects(transform.transformBoundingBox(raster.extent()))
        except Exception:
            logger.debug(
                "Failed to check intersection of %s with the boundary; proceeding "
                "without the check", raster.name(), exc_info=True,
            )
            return True

    def _warp(self, raster):
        suffix = uuid.uuid4().hex[:_TEMP_NAME_HEX_CHARS]
        warp_path = os.path.join(self._scratch_dir, f"_pz_warp_{suffix}.tif")
        warped = _warp_via_processing(raster, self._grid, warp_path, self._steps.run)
        if warped is None:
            warped = _warp_via_gdal(raster, self._grid, warp_path)
        return warped

    def _clip(self, warp_path, source_name):
        clip_path = os.path.join(self._scratch_dir, f"{source_name}_clip.tif")
        self._steps.run("gdal:cliprasterbymasklayer", {
            "INPUT": warp_path,
            "MASK": self._boundary,
            "SOURCE_CRS": self._grid.authid,
            "TARGET_CRS": self._grid.authid,
            "RESAMPLING": _RESAMPLE_NEAREST,
            "NODATA": None,
            "ALPHA_BAND": False,
            "CROP_TO_CUTLINE": True,
            "KEEP_RESOLUTION": True,
            "TARGET_RESOLUTION": None,
            "OUTPUT": clip_path,
        })

        # The clipped layer's name becomes the sampled column prefix downstream.
        layer = QgsRasterLayer(clip_path, f"{source_name}_clip")
        if not layer.isValid():
            raise Exception(tr("Invalid output layer."))
        return layer


def _pixel_centroids(reference_raster, run):
    output = run("native:pixelstopoints", {
        "INPUT_RASTER": reference_raster.source(),
        "RASTER_BAND": _FIRST_BAND,
        "FIELD_NAME": "valor",
        "OUTPUT": "TEMPORARY_OUTPUT",
    })["OUTPUT"]

    layer = (
        QgsVectorLayer(output, "Pontos_centroides", "ogr")
        if isinstance(output, str) else output
    )
    if not layer.isValid():
        raise Exception(tr("Invalid points layer."))
    return layer


def _sample_rasters(points_layer, rasters, steps):
    """Add one column per raster to ``points_layer``, sampled at each point."""
    for raster in rasters:
        steps.check_cancel()
        field_name = raster.name()
        steps.say(tr("Processing"),
                  tr("Extracting values from {}...").format(field_name))

        output = steps.run("qgis:rastersampling", {
            "INPUT": points_layer,
            "RASTERCOPY": raster,
            "COLUMN_PREFIX": field_name + "_",
            "OUTPUT": "TEMPORARY_OUTPUT",
        })["OUTPUT"]

        points_layer = (
            QgsVectorLayer(output, "Amostras_atribuidas", "ogr")
            if isinstance(output, str) else output
        )
        if not points_layer.isValid():
            raise Exception(
                tr("Failed to load layer with values from {}.").format(field_name)
            )
    return points_layer
