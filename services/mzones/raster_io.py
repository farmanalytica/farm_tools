# -*- coding: utf-8 -*-
"""Raster / geotransform helpers shared by services and the export controller.

Consolidates logic that was duplicated between precision_zones.py and the
dialog (geotransform math, xy->rowcol, GeoTIFF writing, layer lookups).
"""
import math

import numpy as np
from osgeo import gdal, osr

from qgis.core import (
    QgsProject, QgsRasterLayer, QgsCoordinateReferenceSystem,
    QgsCoordinateTransform, QgsPointXY,
)

from .i18n import tr


def _finite_number(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _extent_bounds(extent):
    return (
        extent.xMinimum(),
        extent.xMaximum(),
        extent.yMinimum(),
        extent.yMaximum(),
    )


def _validate_extent(extent):
    x_min, x_max, y_min, y_max = _extent_bounds(extent)
    values = (x_min, x_max, y_min, y_max)
    if not all(_finite_number(value) for value in values):
        raise ValueError(
            tr("Boundary extent is invalid. Check that the boundary layer has valid geometry.")
        )
    if x_max <= x_min or y_max <= y_min:
        raise ValueError(
            tr("Boundary extent has zero area. Check that the boundary layer has valid geometry.")
        )
    return x_min, x_max, y_min, y_max


def obter_raster_por_nome(nome):
    for camada in QgsProject.instance().mapLayers().values():
        if isinstance(camada, QgsRasterLayer) and camada.name() == nome:
            return camada
    return None


def find_layer_by_name(nome):
    """Any layer (raster or vector) matching the given name, else None."""
    for layer in QgsProject.instance().mapLayers().values():
        if layer.name() == nome:
            return layer
    return None


def estimate_utm_crs(layer):
    """Return the appropriate WGS84 / UTM CRS for a layer, from its extent
    centroid (mirrors geopandas estimate_utm_crs). EPSG 326xx N / 327xx S."""
    if hasattr(layer, "updateExtents"):
        layer.updateExtents()
    src = layer.crs()
    ext = layer.extent()
    x_min, x_max, y_min, y_max = _validate_extent(ext)
    cx = (x_min + x_max) / 2.0
    cy = (y_min + y_max) / 2.0

    wgs = QgsCoordinateReferenceSystem.fromEpsgId(4326)
    if src != wgs:
        trf = QgsCoordinateTransform(src, wgs, QgsProject.instance().transformContext())
        pt = trf.transform(QgsPointXY(cx, cy))
        lon, lat = pt.x(), pt.y()
    else:
        lon, lat = cx, cy

    if not (_finite_number(lon) and _finite_number(lat)):
        raise ValueError(
            tr("Boundary extent could not be transformed to WGS84. Check the boundary CRS.")
        )

    zone = int((lon + 180.0) / 6.0) % 60 + 1
    epsg = (32600 if lat >= 0 else 32700) + zone
    return QgsCoordinateReferenceSystem.fromEpsgId(epsg)


def compute_grid(extent, resolucao: float):
    """Snap a grid to the extent + resolution.

    Returns (geotransform, (rows, cols)).
    """
    if not _finite_number(resolucao) or float(resolucao) <= 0:
        raise ValueError(tr("Resolution must be a positive number."))
    resolucao = float(resolucao)
    x_min, x_max, y_min, y_max = _validate_extent(extent)

    x0 = math.floor(x_min / resolucao) * resolucao
    y0 = math.ceil(y_max / resolucao) * resolucao
    cols = int(math.ceil((x_max - x0) / resolucao))
    rows = int(math.ceil((y0 - y_min) / resolucao))

    gt = (x0, resolucao, 0.0, y0, 0.0, -resolucao)
    return gt, (rows, cols)


def xy_to_rowcol(gt, x: float, y: float):
    """Convert (X, Y) to (row, col) using a geotransform. None on failure."""
    if gt is None:
        return None
    if not (_finite_number(x) and _finite_number(y)):
        return None
    try:
        col = int((x - gt[0]) / gt[1])
        row = int((y - gt[3]) / gt[5])  # gt[5] is usually negative
        return (row, col)
    except Exception:
        return None


def read_ref_metadata_from_layer(ref_layer):
    """Return (gt, crs_wkt, (rows, cols)) from a raster layer, or None."""
    try:
        ref_path = ref_layer.dataProvider().dataSourceUri().split("|")[0]
        ds = gdal.Open(ref_path)
        if ds is None:
            return None
        return ds.GetGeoTransform(), ds.GetProjection(), (ds.RasterYSize, ds.RasterXSize)
    except Exception:
        return None


def write_geotiff(array2d, geotransform, crs_wkt, out_path,
                  nodata_value: float = -9999.0):
    """Write a single-band Float32 GeoTIFF from a 2D array + reference metadata."""
    rows, cols = array2d.shape
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(out_path, cols, rows, 1, gdal.GDT_Float32,
                       options=["COMPRESS=LZW", "TILED=YES"])
    if ds is None:
        raise RuntimeError(tr("Could not create output GeoTIFF."))
    ds.SetGeoTransform(geotransform)

    if crs_wkt:
        srs = osr.SpatialReference()
        srs.ImportFromWkt(crs_wkt)
        ds.SetProjection(srs.ExportToWkt())

    band = ds.GetRasterBand(1)
    band.WriteArray(array2d)
    band.SetNoDataValue(nodata_value)
    band.FlushCache()

    ds.FlushCache()
    ds = None
