# -*- coding: utf-8 -*-
"""Variance-reduction (VR) per-zone statistics. Pure backend (no QMessageBox)."""
import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from osgeo import gdal

from .deps import import_pandas
from .i18n import tr


@dataclass
class VarianceResult:
    ui_rows: list          # [(zona, media, var, n, area_ha), ...]
    export_df: Any         # full per-zone stats DataFrame (translated columns)
    vr_percent: float
    dropped: int           # points outside the zones raster bbox


class NoZonesData(Exception):
    """Raised when no valid points map to zones (controller shows a warning)."""


def _stats_funcs(pd):
    try:
        from scipy.stats import t as student_t, skew as scipy_skew

        def ic95(media, std, n):
            if n <= 1 or std is None or np.isnan(std):
                return (np.nan, np.nan)
            crit = float(student_t.ppf(0.975, df=n - 1))
            erro = crit * std / math.sqrt(n)
            return (media - erro, media + erro)

        def skewness(arr):
            return float(scipy_skew(arr, bias=False)) if len(arr) >= 3 else np.nan
    except Exception:
        def ic95(media, std, n):
            if n <= 1 or std is None or np.isnan(std):
                return (np.nan, np.nan)
            crit = 1.96
            erro = crit * std / math.sqrt(n)
            return (media - erro, media + erro)

        def skewness(arr):
            s = pd.Series(arr, dtype="float64")
            return float(s.skew()) if s.count() >= 3 else np.nan
    return ic95, skewness


def variance_reduction(df_points, col_x: str, col_y: str, col_attr: str,
                       zones_raster_path: str) -> VarianceResult:
    """Compute per-zone statistics and the variance-reduction percentage.

    Raises NoZonesData when no valid values map to zones; ValueError(translated)
    for empty/out-of-bounds inputs; generic Exception otherwise."""
    pd = import_pandas()
    ic95, skewness = _stats_funcs(pd)

    colZona = tr("Zone")
    colMedia = tr("Mean")
    colVar = tr("Variance")
    colN = "n"
    colArea = tr("Area (ha)")
    colAreaPct = tr("Area (%)")
    colMediana = tr("Median")
    colCV = tr("CV (%)")
    colMin = tr("Min")
    colMax = tr("Max")
    colIClo = tr("95% CI low")
    colICup = tr("95% CI high")

    raster_ds = gdal.Open(zones_raster_path)
    if raster_ds is None:
        raise ValueError(tr("Failed to open zones raster."))

    gt = raster_ds.GetGeoTransform()
    px_w, px_h = gt[1], gt[5]
    pixel_area = abs(px_w * px_h)
    band = raster_ds.GetRasterBand(1)
    zona_array = band.ReadAsArray().astype(float)
    nodata = band.GetNoDataValue()

    df_pontos = df_points.copy()
    for c in [col_x, col_y, col_attr]:
        df_pontos[c] = pd.to_numeric(df_pontos[c], errors="coerce")
    df_pontos = df_pontos.dropna(subset=[col_x, col_y, col_attr])

    x_min, y_max = gt[0], gt[3]
    x_max = x_min + px_w * raster_ds.RasterXSize
    y_min = y_max + px_h * raster_ds.RasterYSize
    mask_bbox = (
        df_pontos[col_x].between(min(x_min, x_max), max(x_min, x_max)) &
        df_pontos[col_y].between(min(y_min, y_max), max(y_min, y_max))
    )
    dropped = int((~mask_bbox).sum())
    df_pontos = df_pontos.loc[mask_bbox].copy()
    if df_pontos.empty:
        raise ValueError(tr("All points are outside the zones raster."))

    zona_valores = {}
    for _, row in df_pontos.iterrows():
        x, y, valor = float(row[col_x]), float(row[col_y]), float(row[col_attr])
        try:
            col_pix = int((x - gt[0]) / gt[1])
            row_pix = int((y - gt[3]) / gt[5])
            z = float(zona_array[row_pix, col_pix])
            if not np.isfinite(z):
                continue
            if nodata is not None and z == nodata:
                continue
            if z <= 0:
                continue
            zona_valores.setdefault(int(z), []).append(valor)
        except Exception:
            continue

    if not zona_valores:
        raise NoZonesData(tr("No valid values were identified in the zones."))

    vals = zona_array
    valid_mask = np.isfinite(vals) & (vals > 0)
    if nodata is not None:
        valid_mask &= (vals != nodata)
    zona_ids, zona_counts = np.unique(vals[valid_mask].astype(int), return_counts=True)
    area_por_zona_m2 = dict(zip(zona_ids, zona_counts * pixel_area))

    ui_rows = []
    area_list = []
    var_list = []
    for z in sorted(zona_valores.keys()):
        s = pd.Series(zona_valores[z], dtype="float64")
        media = float(s.mean())
        var = float(s.var()) if s.count() > 1 else 0.0
        n = int(s.count())
        area_ha = (area_por_zona_m2.get(int(z), np.nan) / 10000.0
                   if int(z) in area_por_zona_m2 else np.nan)
        ui_rows.append((int(z), media, var, n, area_ha))
        area_list.append(area_ha)
        var_list.append(var)

    todos_valores = np.concatenate([np.asarray(v, dtype=float) for v in zona_valores.values()])
    var_total = float(pd.Series(todos_valores).var()) if len(todos_valores) > 1 else 0.0
    area_total_ha = float(np.nansum(area_list))
    if area_total_ha > 0:
        termo = float(np.nansum([(a / area_total_ha) * v
                                 for a, v in zip(area_list, var_list)]))
    else:
        termo = 0.0
    vr_percent = (1 - (termo / var_total)) * 100 if var_total > 0 else 0.0

    linhas_export = []
    for z in sorted(zona_valores.keys()):
        arr = np.asarray(zona_valores[z], dtype=float)
        s = pd.Series(arr, dtype="float64")
        n = int(s.count())
        media = float(s.mean())
        std = float(s.std(ddof=1)) if n > 1 else np.nan
        mediana = float(s.median())
        q1 = float(s.quantile(0.25))
        q3 = float(s.quantile(0.75))
        iqr = q3 - q1
        vmin = float(s.min())
        vmax = float(s.max())
        cv = float((std / media * 100.0)) if (n > 1 and media != 0) else np.nan
        sk = skewness(arr)
        ic_inf, ic_sup = ic95(media, std, n)
        area_ha = (area_por_zona_m2.get(int(z), np.nan) / 10000.0
                   if int(z) in area_por_zona_m2 else np.nan)
        area_pct = (area_ha / area_total_ha * 100.0) if (area_total_ha and not np.isnan(area_ha)) else np.nan
        var = float(s.var()) if n > 1 else 0.0

        linhas_export.append({
            colZona: int(z), colN: n, colArea: area_ha, colAreaPct: area_pct,
            colMedia: media, colMediana: mediana, colCV: cv, colMin: vmin,
            "Q1": q1, "Q3": q3, colMax: vmax, "IQR": iqr, "Skewness": sk,
            colIClo: ic_inf, colICup: ic_sup, colVar: var
        })

    export_df = pd.DataFrame(linhas_export)
    return VarianceResult(ui_rows=ui_rows, export_df=export_df,
                          vr_percent=vr_percent, dropped=dropped)
