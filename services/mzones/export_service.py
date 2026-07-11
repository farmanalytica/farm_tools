# -*- coding: utf-8 -*-
"""Export helpers: CSV, PCA report, boxplots PNG, PC rasters. Pure backend."""
import os

import numpy as np
from osgeo import gdal, osr

from .deps import import_pandas
from .i18n import tr
from .raster_io import write_geotiff, xy_to_rowcol


class NoPointsInZones(Exception):
    """Raised when points cannot be mapped to zones for a plot."""


def save_dataframe_csv(df, path, **kwargs):
    df.to_csv(path, **kwargs)


def save_pca_report(relatorio_pca, variancia_explicada, folder):
    """Write pca_componentes.csv + pca_variancia.csv. Returns the folder."""
    f1 = os.path.join(folder, "pca_componentes.csv")
    f2 = os.path.join(folder, "pca_variancia.csv")
    relatorio_pca.to_csv(f1, index=False, encoding="utf-8-sig")
    variancia_explicada.to_csv(f2, index=False, encoding="utf-8-sig")
    return folder


def build_boxplots(df_points, col_x: str, col_y: str, col_attr: str,
                   zones_raster_path: str, out_path: str):
    """Render 'all vs per-zone' boxplots to a PNG. Raises ValueError/NoPointsInZones."""
    pd = import_pandas()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ds = gdal.Open(zones_raster_path)
    if ds is None:
        raise ValueError(tr("Failed to open zones raster."))

    gt = ds.GetGeoTransform()
    band = ds.GetRasterBand(1)
    zona_array = band.ReadAsArray().astype(float)
    nodata = band.GetNoDataValue()

    df_pontos = df_points.copy()
    for c in [col_x, col_y, col_attr]:
        df_pontos[c] = pd.to_numeric(df_pontos[c], errors='coerce')
    df_pontos = df_pontos.dropna(subset=[col_x, col_y, col_attr])

    x_min, y_max = gt[0], gt[3]
    px_w, px_h = gt[1], gt[5]
    x_max = x_min + px_w * ds.RasterXSize
    y_min = y_max + px_h * ds.RasterYSize
    mask_bbox = (
        df_pontos[col_x].between(min(x_min, x_max), max(x_min, x_max)) &
        df_pontos[col_y].between(min(y_min, y_max), max(y_min, y_max))
    )
    df_pontos = df_pontos.loc[mask_bbox].copy()
    if df_pontos.empty:
        raise ValueError(tr("All points are outside the zones raster."))

    registros = []
    for _, row in df_pontos.iterrows():
        x, y, valor = float(row[col_x]), float(row[col_y]), float(row[col_attr])
        try:
            c = int((x - gt[0]) / gt[1])
            r = int((y - gt[3]) / gt[5])
            z = float(zona_array[r, c])
            if not np.isfinite(z):
                continue
            if nodata is not None and z == nodata:
                continue
            if z <= 0:
                continue
            registros.append((int(z), float(valor)))
        except Exception:
            continue

    if not registros:
        raise NoPointsInZones(tr("Could not map points to zones for the boxplot."))

    colZona = tr("Zone")
    colValor = tr("Value")
    dfz = pd.DataFrame(registros, columns=[colZona, colValor]).dropna()

    series = [dfz[colValor].values] + [
        dfz.loc[dfz[colZona] == z, colValor].values
        for z in sorted(dfz[colZona].unique())
    ]
    labels = [tr("All")] + [f"Z{z}" for z in sorted(dfz[colZona].unique())]

    nplots = len(series)
    fig_w = max(6, 1.8 * nplots)
    fig, ax = plt.subplots(figsize=(fig_w, 4))
    ax.boxplot(series, showfliers=True)
    ax.set_xticklabels(labels)
    ax.set_xlabel(tr("Groups"))
    ax.set_ylabel(col_attr)
    ax.set_title(tr("Boxplots – {} (All vs. Zones)").format(col_attr))
    ax.grid(True, axis='y', linestyle='--', alpha=0.4)
    plt.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches='tight')
    plt.close(fig)


def export_pc_raster(scores, pc_idx: int, df, ref_gt, ref_crs_wkt, grid_shape, out_path):
    """Write a single-band GeoTIFF for the chosen PC."""
    rows, cols = grid_shape
    nodata_value = -9999.0
    arr = np.full((rows, cols), nodata_value, dtype=np.float32)

    min_n = min(len(df), scores.shape[0])
    vals = scores[:min_n, pc_idx].astype(np.float32)

    for i, (x, y) in enumerate(df.loc[:min_n - 1, ["X", "Y"]].itertuples(index=False, name=None)):
        rc = xy_to_rowcol(ref_gt, float(x), float(y))
        if rc is None:
            continue
        r, c = rc
        if 0 <= r < rows and 0 <= c < cols:
            arr[r, c] = vals[i]

    write_geotiff(arr, ref_gt, ref_crs_wkt, out_path, nodata_value=nodata_value)


def export_all_pcs_multiband(scores, df, ref_gt, ref_crs_wkt, grid_shape, out_path):
    """Write a multiband GeoTIFF with one band per PC."""
    rows, cols = grid_shape
    nb = scores.shape[1] if hasattr(scores, "shape") and len(scores.shape) == 2 else 0
    nodata_value = -9999.0

    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(out_path, cols, rows, nb, gdal.GDT_Float32,
                       options=["COMPRESS=LZW", "TILED=YES"])
    if ds is None:
        raise RuntimeError(tr("Failed to create multiband GeoTIFF."))

    ds.SetGeoTransform(ref_gt)
    if ref_crs_wkt:
        srs = osr.SpatialReference()
        srs.ImportFromWkt(ref_crs_wkt)
        ds.SetProjection(srs.ExportToWkt())

    min_n = min(len(df), scores.shape[0])
    for b in range(nb):
        band_arr = np.full((rows, cols), nodata_value, dtype=np.float32)
        vals = scores[:min_n, b].astype(np.float32)
        for i, (x, y) in enumerate(df.loc[:min_n - 1, ["X", "Y"]].itertuples(index=False, name=None)):
            rc = xy_to_rowcol(ref_gt, float(x), float(y))
            if rc is None:
                continue
            r, c = rc
            if 0 <= r < rows and 0 <= c < cols:
                band_arr[r, c] = vals[i]
        rb = ds.GetRasterBand(b + 1)
        rb.WriteArray(band_arr)
        rb.SetNoDataValue(nodata_value)
        rb.SetDescription(f"PC{b+1}")
        rb.FlushCache()

    ds.FlushCache()
    ds = None
