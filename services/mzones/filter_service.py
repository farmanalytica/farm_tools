# -*- coding: utf-8 -*-
"""Majority (modal) filter computed in-process with numpy/scipy, replacing the
old SAGA-based pipeline. Runs directly on the source grid, so no warp/align or
zone-id remapping is needed. Pure backend (no QMessageBox).

Note: the output GeoTIFF lives under a temp dir and is consumed directly as the
new layer's source, so that dir is intentionally not deleted here."""
import os
import tempfile
import uuid
from dataclasses import dataclass
from typing import Optional

import numpy as np
from osgeo import gdal

from .i18n import tr


@dataclass
class FilterResult:
    out_path: str
    nodata: Optional[float]
    raio: int


def _circular_kernel(radius: int) -> np.ndarray:
    """Boolean disc of the given radius (matches SAGA's circle kernel)."""
    r = max(1, int(radius))
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return (x * x + y * y) <= r * r


def apply_majority_filter(src_path: str, raster_crs_authid: str,
                          raio: int, threshold: float = 0.0) -> FilterResult:
    """Apply a circular-kernel majority filter to the zones raster at src_path
    and write a UInt16 GeoTIFF on the same grid. `threshold` is the minimum
    share (percent) of valid neighbours the winning value must hold for a cell
    to be replaced; below it the original value is kept. Raises
    Exception(translated)."""
    try:
        from scipy import ndimage
    except Exception:
        raise Exception(tr("scipy not available. Install dependencies from the Intro page."))

    dsA = gdal.Open(src_path)
    if dsA is None:
        raise Exception(tr("Failed to open input raster."))

    gt = dsA.GetGeoTransform()
    width_px = int(dsA.RasterXSize)
    height_px = int(dsA.RasterYSize)

    bandA = dsA.GetRasterBand(1)
    nodata = bandA.GetNoDataValue()
    arr = bandA.ReadAsArray()
    if arr is None:
        raise Exception(tr("Failed to open input raster."))

    if nodata is not None:
        valid = arr != nodata
        nd_out = nodata
    elif (arr == 0).any():
        valid = arr != 0
        nd_out = 0
    else:
        valid = np.ones_like(arr, dtype=bool)
        nd_out = None

    kernel = _circular_kernel(raio).astype(np.int32)
    vals = np.unique(arr[valid])

    out_arr = arr.copy()
    if vals.size > 1:
        best_count = np.zeros(arr.shape, dtype=np.int32)
        best_val = np.zeros(arr.shape, dtype=arr.dtype)
        total = ndimage.convolve(valid.astype(np.int32), kernel,
                                 mode="constant", cval=0)
        for v in vals:
            count = ndimage.convolve(((arr == v) & valid).astype(np.int32),
                                     kernel, mode="constant", cval=0)
            win = count > best_count
            best_count[win] = count[win]
            best_val[win] = v
            # tie goes to the cell's original value
            tie = (count == best_count) & (arr == v)
            best_val[tie] = v

        replace = valid & (best_count > 0)
        if threshold > 0:
            with np.errstate(divide="ignore", invalid="ignore"):
                share = np.where(total > 0, best_count * 100.0 / total, 0.0)
            replace &= share >= float(threshold)
        out_arr[replace] = best_val[replace]

    base = os.path.join(tempfile.gettempdir(), "pzmod_" + uuid.uuid4().hex[:8])
    os.makedirs(base, exist_ok=True)
    p_out = os.path.join(base, "m.tif")

    drv = gdal.GetDriverByName("GTiff")
    out_ds = drv.Create(p_out, width_px, height_px, 1, gdal.GDT_UInt16,
                        options=["COMPRESS=LZW", "TILED=YES"])
    out_ds.SetGeoTransform(gt)
    out_ds.SetProjection(dsA.GetProjection())
    out_band = out_ds.GetRasterBand(1)
    if nd_out is not None:
        out_band.SetNoDataValue(float(nd_out))
    out_band.WriteArray(out_arr.astype(np.uint16))
    out_band.FlushCache()
    out_ds.FlushCache()
    out_ds = None

    return FilterResult(out_path=p_out, nodata=nodata, raio=raio)
