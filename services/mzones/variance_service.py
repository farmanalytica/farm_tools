# -*- coding: utf-8 -*-
"""Variance-reduction (VR) per-zone statistics. Pure backend (no QMessageBox)."""
import logging
import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from osgeo import gdal

from .deps import import_pandas
from .i18n import tr

logger = logging.getLogger(__name__)


@dataclass
class VarianceResult:
    ui_rows: list          # [(zona, media, var, n, area_ha), ...]
    export_df: Any         # full per-zone stats DataFrame (translated columns)
    vr_percent: float
    dropped: int           # points outside the zones raster bbox


class NoZonesData(Exception):
    """Raised when no valid points map to zones (controller shows a warning)."""


M2_PER_HECTARE = 10000.0
_MIN_SAMPLES_FOR_SKEW = 3
_CONFIDENCE = 0.95
_TWO_TAILED_QUANTILE = 1 - (1 - _CONFIDENCE) / 2
# Normal-approximation critical value, used when scipy is unavailable.
_NORMAL_CRITICAL = 1.96
_LOWER_QUARTILE = 0.25
_UPPER_QUARTILE = 0.75
_PERCENT = 100.0
# Zone ids are positive; 0 and negatives mark "no zone here".
_NO_ZONE = 0


def _confidence_interval(mean, std, count, critical):
    """The two-sided interval around ``mean``, or NaNs when there is too little data."""
    if count <= 1 or std is None or np.isnan(std):
        return (np.nan, np.nan)
    margin = critical * std / math.sqrt(count)
    return (mean - margin, mean + margin)


def _stats_funcs(pd):
    """``(ic95, skewness)``, backed by scipy when it is available.

    Without scipy the interval falls back to the normal approximation and the
    skew comes from pandas, so the report still renders on a bare install.
    """
    try:
        from scipy.stats import t as student_t, skew as scipy_skew

        def ic95(mean, std, count):
            critical = float(student_t.ppf(_TWO_TAILED_QUANTILE, df=count - 1))
            return _confidence_interval(mean, std, count, critical)

        def skewness(values):
            if len(values) < _MIN_SAMPLES_FOR_SKEW:
                return np.nan
            return float(scipy_skew(values, bias=False))
    except Exception:
        def ic95(mean, std, count):
            return _confidence_interval(mean, std, count, _NORMAL_CRITICAL)

        def skewness(values):
            series = pd.Series(values, dtype="float64")
            if series.count() < _MIN_SAMPLES_FOR_SKEW:
                return np.nan
            return float(series.skew())
    return ic95, skewness




@dataclass(frozen=True)
class _ExportColumns:
    """The translated column headings of the per-zone statistics table."""

    zone: str
    mean: str
    variance: str
    count: str
    area: str
    area_pct: str
    median: str
    cv: str
    minimum: str
    maximum: str
    ci_low: str
    ci_high: str

    @classmethod
    def translated(cls):
        return cls(
            zone=tr("Zone"),
            mean=tr("Mean"),
            variance=tr("Variance"),
            count="n",
            area=tr("Area (ha)"),
            area_pct=tr("Area (%)"),
            median=tr("Median"),
            cv=tr("CV (%)"),
            minimum=tr("Min"),
            maximum=tr("Max"),
            ci_low=tr("95% CI low"),
            ci_high=tr("95% CI high"),
        )


class _ZoneRaster:
    """The zones GeoTIFF, answering "which zone is at this point" and "how big is each zone"."""

    def __init__(self, path):
        dataset = gdal.Open(path)
        if dataset is None:
            raise ValueError(tr("Failed to open zones raster."))

        self._geotransform = dataset.GetGeoTransform()
        band = dataset.GetRasterBand(1)
        self._zones = band.ReadAsArray().astype(float)
        self._nodata = band.GetNoDataValue()

        pixel_width, pixel_height = self._geotransform[1], self._geotransform[5]
        self._pixel_area = abs(pixel_width * pixel_height)
        self._width = dataset.RasterXSize
        self._height = dataset.RasterYSize

    @property
    def bounds(self):
        """``(x_min, x_max, y_min, y_max)`` in the raster's own CRS."""
        x_min, y_max = self._geotransform[0], self._geotransform[3]
        x_max = x_min + self._geotransform[1] * self._width
        y_min = y_max + self._geotransform[5] * self._height
        return x_min, x_max, y_min, y_max

    def zone_at(self, x, y):
        """The zone id covering ``(x, y)``, or ``None`` where there is no zone."""
        column = int((x - self._geotransform[0]) / self._geotransform[1])
        row = int((y - self._geotransform[3]) / self._geotransform[5])
        zone = float(self._zones[row, column])
        if not np.isfinite(zone):
            return None
        if self._nodata is not None and zone == self._nodata:
            return None
        if zone <= _NO_ZONE:
            return None
        return int(zone)

    def area_ha_by_zone(self):
        """``{zone id: area in hectares}`` counted over the whole raster."""
        valid = np.isfinite(self._zones) & (self._zones > _NO_ZONE)
        if self._nodata is not None:
            valid &= self._zones != self._nodata
        zone_ids, pixel_counts = np.unique(
            self._zones[valid].astype(int), return_counts=True
        )
        return {
            int(zone_id): count * self._pixel_area / M2_PER_HECTARE
            for zone_id, count in zip(zone_ids, pixel_counts)
        }


def _clean_points(df_points, columns, bounds, pd):
    """The numeric, in-bounds points, plus how many fell outside the raster."""
    col_x, col_y, col_attr = columns
    points = df_points.copy()
    for column in (col_x, col_y, col_attr):
        points[column] = pd.to_numeric(points[column], errors="coerce")
    points = points.dropna(subset=[col_x, col_y, col_attr])

    x_min, x_max, y_min, y_max = bounds
    inside = (
        points[col_x].between(min(x_min, x_max), max(x_min, x_max))
        & points[col_y].between(min(y_min, y_max), max(y_min, y_max))
    )
    dropped = int((~inside).sum())
    points = points.loc[inside].copy()
    if points.empty:
        raise ValueError(tr("All points are outside the zones raster."))
    return points, dropped


def _values_by_zone(points, columns, zone_raster):
    """``{zone id: [measured values]}`` for every point that lands in a zone."""
    col_x, col_y, col_attr = columns
    by_zone = {}
    for _, row in points.iterrows():
        x, y, value = float(row[col_x]), float(row[col_y]), float(row[col_attr])
        try:
            zone = zone_raster.zone_at(x, y)
        except Exception:
            logger.debug(
                "Failed to map point (x=%s, y=%s) to a zone for variance stats; "
                "skipping", x, y, exc_info=True,
            )
            continue
        if zone is not None:
            by_zone.setdefault(zone, []).append(value)

    if not by_zone:
        raise NoZonesData(tr("No valid values were identified in the zones."))
    return by_zone


def _variance(series, count):
    return float(series.var()) if count > 1 else 0.0


def _reduction_percent(area_ha_list, variance_list, all_values, pd):
    """How much of the field's variance the zoning removes, as a percentage.

    The within-zone variances are weighted by each zone's share of the area,
    and compared against the variance of every measurement together.
    """
    total_variance = (
        float(pd.Series(all_values).var()) if len(all_values) > 1 else 0.0
    )
    if total_variance <= 0:
        return 0.0

    total_area_ha = float(np.nansum(area_ha_list))
    if total_area_ha <= 0:
        return _PERCENT

    within_zone_variance = float(np.nansum([
        (area / total_area_ha) * variance
        for area, variance in zip(area_ha_list, variance_list)
    ]))
    return (1 - (within_zone_variance / total_variance)) * _PERCENT


def _export_row(zone, values, area_ha, context):
    """One fully-described zone: spread, shape, confidence interval, area share."""
    pd, columns, total_area_ha, ic95, skewness = context
    array = np.asarray(values, dtype=float)
    series = pd.Series(array, dtype="float64")

    count = int(series.count())
    mean = float(series.mean())
    std = float(series.std(ddof=1)) if count > 1 else np.nan
    q1 = float(series.quantile(_LOWER_QUARTILE))
    q3 = float(series.quantile(_UPPER_QUARTILE))
    cv = float(std / mean * _PERCENT) if (count > 1 and mean != 0) else np.nan
    ci_low, ci_high = ic95(mean, std, count)
    area_pct = (
        area_ha / total_area_ha * _PERCENT
        if (total_area_ha and not np.isnan(area_ha)) else np.nan
    )

    return {
        columns.zone: zone,
        columns.count: count,
        columns.area: area_ha,
        columns.area_pct: area_pct,
        columns.mean: mean,
        columns.median: float(series.median()),
        columns.cv: cv,
        columns.minimum: float(series.min()),
        "Q1": q1,
        "Q3": q3,
        columns.maximum: float(series.max()),
        "IQR": q3 - q1,
        "Skewness": skewness(array),
        columns.ci_low: ci_low,
        columns.ci_high: ci_high,
        columns.variance: _variance(series, count),
    }


def variance_reduction(df_points, col_x: str, col_y: str, col_attr: str,
                       zones_raster_path: str) -> VarianceResult:
    """Compute per-zone statistics and the variance-reduction percentage.

    Raises NoZonesData when no valid values map to zones; ValueError(translated)
    for empty/out-of-bounds inputs; generic Exception otherwise."""
    pd = import_pandas()
    ic95, skewness = _stats_funcs(pd)
    columns = _ExportColumns.translated()
    point_columns = (col_x, col_y, col_attr)

    zone_raster = _ZoneRaster(zones_raster_path)
    points, dropped = _clean_points(df_points, point_columns, zone_raster.bounds, pd)
    values_by_zone = _values_by_zone(points, point_columns, zone_raster)
    area_ha_by_zone = zone_raster.area_ha_by_zone()

    zones = sorted(values_by_zone)
    areas_ha = [area_ha_by_zone.get(zone, np.nan) for zone in zones]

    ui_rows = []
    variances = []
    for zone, area_ha in zip(zones, areas_ha):
        series = pd.Series(values_by_zone[zone], dtype="float64")
        count = int(series.count())
        variance = _variance(series, count)
        ui_rows.append((zone, float(series.mean()), variance, count, area_ha))
        variances.append(variance)

    all_values = np.concatenate(
        [np.asarray(values, dtype=float) for values in values_by_zone.values()]
    )
    vr_percent = _reduction_percent(areas_ha, variances, all_values, pd)

    total_area_ha = float(np.nansum(areas_ha))
    context = (pd, columns, total_area_ha, ic95, skewness)
    export_df = pd.DataFrame([
        _export_row(zone, values_by_zone[zone], area_ha, context)
        for zone, area_ha in zip(zones, areas_ha)
    ])

    return VarianceResult(ui_rows=ui_rows, export_df=export_df,
                          vr_percent=vr_percent, dropped=dropped)
