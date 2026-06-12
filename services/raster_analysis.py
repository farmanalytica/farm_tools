# -*- coding: utf-8 -*-
"""Low-level raster analysis helpers for raster-based optimal point selection.

All functions here are headless and operate on one polygon at a time:
read a pixel-aligned raster block clipped to the polygon bounding box,
rasterize the polygon to a binary mask (scanline intersection, exact
geometry, holes and multipolygons included), smooth, and locate the
maximum-value pixel. Coordinates stay in the raster CRS; callers handle
any reprojection to WGS84.
"""

import math

import numpy as np

from qgis.core import Qgis, QgsGeometry, QgsPointXY, QgsRectangle

# Cap on pixels read per polygon; larger requests are resampled by the
# provider so memory stays bounded for very large features.
MAX_PIXELS_PER_POLYGON = 4_000_000

_QGIS_TO_NUMPY_DTYPE = {
    Qgis.DataType.Byte: np.uint8,
    Qgis.DataType.UInt16: np.uint16,
    Qgis.DataType.Int16: np.int16,
    Qgis.DataType.UInt32: np.uint32,
    Qgis.DataType.Int32: np.int32,
    Qgis.DataType.Float32: np.float32,
    Qgis.DataType.Float64: np.float64,
}
if hasattr(Qgis.DataType, 'Int8'):
    _QGIS_TO_NUMPY_DTYPE[Qgis.DataType.Int8] = np.int8


def raster_layer_supports_analysis(raster_layer):
    """Return True when the raster has a readable fixed-size pixel grid.

    Web rendering providers (WMS, XYZ tiles) expose no native grid and
    cannot be sampled for per-pixel statistics.
    """
    if raster_layer is None or not raster_layer.isValid():
        return False
    if raster_layer.bandCount() < 1:
        return False
    return raster_layer.width() > 0 and raster_layer.height() > 0


def find_polygon_maximum(raster_layer, polygon_geom, band_index):
    """Find the maximum-value pixel of one polygon, in the raster CRS.

    ``polygon_geom`` must already be expressed in the raster CRS.

    Returns a dict ``{'x', 'y', 'value', 'sub_pixel', 'no_data_pixels'}``
    or ``None`` when the polygon holds no valid raster data. ``sub_pixel``
    flags polygons smaller than the raster resolution, where the point is
    the center of the single covering pixel.

    Algorithm: clip a pixel-aligned block to the polygon bounding box,
    build an exact binary polygon mask, drop no-data pixels, apply a 3x3
    morphological opening to the mask and a 3x3 mean smoothing to the
    values to suppress edge noise, then take the argmax of the smoothed
    surface restricted to the mask. The reported value is the raw
    (unsmoothed) raster value at the chosen pixel.
    """
    block_info = read_polygon_block(raster_layer, polygon_geom, band_index)
    if block_info is None:
        return None
    values, valid, sub_extent, block_width, block_height = block_info

    polygon_mask = rasterize_polygon_mask(
        polygon_geom, sub_extent, block_width, block_height
    )
    mask = polygon_mask & valid
    no_data_pixels = int(np.count_nonzero(polygon_mask & ~valid))

    if not mask.any():
        return _sub_pixel_fallback(
            polygon_geom, values, valid, sub_extent,
            block_width, block_height, no_data_pixels,
        )

    location = find_maximum_in_masked_array(values, mask)
    if location is None:
        return None
    row, col = location
    x, y = pixel_to_world_coordinates(
        row, col, sub_extent, block_width, block_height
    )
    return {
        'x': x,
        'y': y,
        'value': float(values[row, col]),
        'sub_pixel': False,
        'no_data_pixels': no_data_pixels,
    }


def read_polygon_block(raster_layer, polygon_geom, band_index):
    """Read a pixel-aligned raster block covering the polygon bounding box.

    Returns ``(values, valid, sub_extent, width, height)`` where ``values``
    is a float64 array, ``valid`` a boolean no-data mask, or ``None`` when
    the polygon falls outside the raster or the block cannot be read.
    """
    provider = raster_layer.dataProvider()
    if provider is None:
        return None

    raster_extent = raster_layer.extent()
    bounds = polygon_geom.boundingBox()
    if not bounds.intersects(raster_extent):
        return None

    pixel_x = raster_layer.rasterUnitsPerPixelX()
    pixel_y = raster_layer.rasterUnitsPerPixelY()
    if pixel_x <= 0 or pixel_y <= 0:
        return None

    raster_width = raster_layer.width()
    raster_height = raster_layer.height()

    col_start = int(math.floor((bounds.xMinimum() - raster_extent.xMinimum()) / pixel_x))
    col_end = int(math.ceil((bounds.xMaximum() - raster_extent.xMinimum()) / pixel_x))
    row_start = int(math.floor((raster_extent.yMaximum() - bounds.yMaximum()) / pixel_y))
    row_end = int(math.ceil((raster_extent.yMaximum() - bounds.yMinimum()) / pixel_y))

    col_start = max(0, min(raster_width - 1, col_start))
    row_start = max(0, min(raster_height - 1, row_start))
    col_end = max(col_start + 1, min(raster_width, col_end))
    row_end = max(row_start + 1, min(raster_height, row_end))

    block_width = col_end - col_start
    block_height = row_end - row_start

    sub_extent = QgsRectangle(
        raster_extent.xMinimum() + col_start * pixel_x,
        raster_extent.yMaximum() - row_end * pixel_y,
        raster_extent.xMinimum() + col_end * pixel_x,
        raster_extent.yMaximum() - row_start * pixel_y,
    )

    total_pixels = block_width * block_height
    if total_pixels > MAX_PIXELS_PER_POLYGON:
        scale = math.sqrt(MAX_PIXELS_PER_POLYGON / float(total_pixels))
        block_width = max(1, int(block_width * scale))
        block_height = max(1, int(block_height * scale))

    block = provider.block(band_index, sub_extent, block_width, block_height)
    if block is None or not block.isValid():
        return None

    dtype = _QGIS_TO_NUMPY_DTYPE.get(block.dataType())
    if dtype is None:
        return None

    raw = bytes(block.data())
    expected_size = block_width * block_height * np.dtype(dtype).itemsize
    if len(raw) < expected_size:
        return None
    values = np.frombuffer(raw[:expected_size], dtype=dtype).reshape(
        block_height, block_width
    ).astype(np.float64)

    valid = np.isfinite(values)
    no_data_value = None
    if block.hasNoDataValue():
        no_data_value = block.noDataValue()
    elif provider.sourceHasNoDataValue(band_index):
        no_data_value = provider.sourceNoDataValue(band_index)
    if no_data_value is not None and math.isfinite(no_data_value):
        valid &= ~np.isclose(values, no_data_value, rtol=0.0, atol=1e-9)

    return values, valid, sub_extent, block_width, block_height


def rasterize_polygon_mask(polygon_geom, extent, width, height):
    """Rasterize a polygon to an exact binary mask (True = pixel center inside).

    Uses per-row scanline intersection with the polygon geometry, which
    keeps holes and multipart polygons exact without interpolation.
    """
    mask = np.zeros((height, width), dtype=bool)
    pixel_x = extent.width() / float(width)
    pixel_y = extent.height() / float(height)
    x_origin = extent.xMinimum()
    y_top = extent.yMaximum()
    column_centers = x_origin + (np.arange(width) + 0.5) * pixel_x

    line_start = x_origin - pixel_x
    line_end = extent.xMaximum() + pixel_x

    for row in range(height):
        y = y_top - (row + 0.5) * pixel_y
        scanline = QgsGeometry.fromPolylineXY(
            [QgsPointXY(line_start, y), QgsPointXY(line_end, y)]
        )
        intersection = polygon_geom.intersection(scanline)
        if intersection is None or intersection.isEmpty():
            continue
        for x_min, x_max in _iter_segment_ranges(intersection):
            mask[row, (column_centers >= x_min) & (column_centers <= x_max)] = True

    return mask


def _iter_segment_ranges(geometry):
    """Yield (x_min, x_max) ranges from a scanline intersection result."""
    if geometry.isMultipart():
        parts = geometry.asGeometryCollection()
    else:
        parts = [geometry]

    for part in parts:
        polyline = part.asPolyline()
        if polyline:
            xs = [point.x() for point in polyline]
            yield min(xs), max(xs)


def binary_opening_3x3(mask):
    """Morphological opening (erosion then dilation) with a 3x3 kernel.

    Border pixels are treated as outside during erosion, which removes
    one-pixel noise and spurs at polygon edges.
    """
    eroded = _shift_reduce(mask, np.logical_and)
    if not eroded.any():
        return mask
    return _shift_reduce(eroded, np.logical_or)


def smooth_mean_3x3(values, valid):
    """Mean-smooth values over a 3x3 window restricted to valid pixels.

    Invalid neighbors are excluded from each window average so no-data
    never bleeds into the smoothed surface. Returns a float64 array with
    NaN where no valid neighbor exists.
    """
    filled = np.where(valid, values, 0.0)
    weight = valid.astype(np.float64)
    total = np.zeros_like(filled)
    count = np.zeros_like(weight)
    for row_shift in (-1, 0, 1):
        for col_shift in (-1, 0, 1):
            total += _shifted(filled, row_shift, col_shift, 0.0)
            count += _shifted(weight, row_shift, col_shift, 0.0)
    with np.errstate(invalid='ignore', divide='ignore'):
        smoothed = total / count
    smoothed[count == 0] = np.nan
    return smoothed


def find_maximum_in_masked_array(values, mask):
    """Return (row, col) of the maximum value within the boolean mask.

    Applies a 3x3 morphological opening to the mask and a 3x3 mean
    smoothing to the values before locating the peak, so single-pixel
    noise and edge artifacts do not drive the selection. Returns ``None``
    when the mask is empty.
    """
    if not mask.any():
        return None

    search_mask = binary_opening_3x3(mask)
    if not search_mask.any():
        search_mask = mask

    smoothed = smooth_mean_3x3(values, mask)
    candidate = np.where(search_mask, smoothed, np.nan)
    if not np.isfinite(candidate).any():
        candidate = np.where(mask, values, np.nan)
        if not np.isfinite(candidate).any():
            return None

    flat_index = int(np.nanargmax(candidate))
    return np.unravel_index(flat_index, candidate.shape)


def pixel_to_world_coordinates(pixel_row, pixel_col, raster_extent, raster_width, raster_height):
    """Convert a pixel (row, col) to its center (x, y) in the raster CRS."""
    pixel_x = raster_extent.width() / float(raster_width)
    pixel_y = raster_extent.height() / float(raster_height)
    x = raster_extent.xMinimum() + (pixel_col + 0.5) * pixel_x
    y = raster_extent.yMaximum() - (pixel_row + 0.5) * pixel_y
    return x, y


def _sub_pixel_fallback(
    polygon_geom, values, valid, sub_extent, width, height, no_data_pixels
):
    """Handle polygons smaller than one pixel: use the covering pixel center.

    Locates the pixel containing the polygon's interior point; if that
    pixel holds valid data its center becomes the sampling point.
    """
    interior = polygon_geom.pointOnSurface()
    if interior is None or interior.isEmpty():
        return None
    point = interior.asPoint()

    pixel_x = sub_extent.width() / float(width)
    pixel_y = sub_extent.height() / float(height)
    col = int((point.x() - sub_extent.xMinimum()) / pixel_x)
    row = int((sub_extent.yMaximum() - point.y()) / pixel_y)
    col = max(0, min(width - 1, col))
    row = max(0, min(height - 1, row))

    if not valid[row, col]:
        return None

    x, y = pixel_to_world_coordinates(row, col, sub_extent, width, height)
    return {
        'x': x,
        'y': y,
        'value': float(values[row, col]),
        'sub_pixel': True,
        'no_data_pixels': no_data_pixels,
    }


def _shift_reduce(mask, operation):
    """Reduce a boolean mask over its 3x3 neighborhood with the operation."""
    result = None
    # Erosion treats out-of-bounds as False; dilation also pads with False.
    for row_shift in (-1, 0, 1):
        for col_shift in (-1, 0, 1):
            shifted = _shifted(mask, row_shift, col_shift, False)
            result = shifted if result is None else operation(result, shifted)
    return result


def _shifted(array, row_shift, col_shift, fill_value):
    """Return the array shifted by (row_shift, col_shift) with constant fill."""
    result = np.full_like(array, fill_value)
    rows, cols = array.shape

    src_row_start = max(0, -row_shift)
    src_row_end = rows - max(0, row_shift)
    src_col_start = max(0, -col_shift)
    src_col_end = cols - max(0, col_shift)
    if src_row_start >= src_row_end or src_col_start >= src_col_end:
        return result

    dst_row_start = max(0, row_shift)
    dst_row_end = dst_row_start + (src_row_end - src_row_start)
    dst_col_start = max(0, col_shift)
    dst_col_end = dst_col_start + (src_col_end - src_col_start)

    result[dst_row_start:dst_row_end, dst_col_start:dst_col_end] = (
        array[src_row_start:src_row_end, src_col_start:src_col_end]
    )
    return result
