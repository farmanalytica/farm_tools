# -*- coding: utf-8 -*-
"""Resampling + extraction service: warp/clip rasters to a snapped grid, sample
pixel centroids into a points DataFrame. Pure backend (no QMessageBox)."""
import os
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


def resample_and_extract(contorno_layer, rasters, resolucao: float,
                         progress: Optional[Callable] = None) -> ResampleResult:
    """Warp/resample + clip each raster to the boundary grid, then sample
    pixel-centroid points across all rasters into a DataFrame.

    `progress(title, msg, level)` is an optional status sink.
    Raises Exception(translated) on hard failures.
    """
    pd = import_pandas()

    def _say(title, msg, level=0):
        if progress:
            progress(title, msg, level)

    context = QgsProcessingContext()
    context.setTransformContext(QgsProject.instance().transformContext())
    feedback = QgsProcessingFeedback()

    # 0) auto-reproject a geographic boundary to its appropriate UTM CRS so the
    #    resolution (meters) and metric grid are well defined. Silent by design:
    #    the conversion is an implementation detail the user never acts on.
    reprojected = False
    if contorno_layer.crs().isGeographic():
        reprojected = True
        utm = estimate_utm_crs(contorno_layer)
        rep = processing.run("native:reprojectlayer", {
            "INPUT": contorno_layer,
            "TARGET_CRS": utm,
            "OUTPUT": "memory:boundary_utm",
        }, context=context, feedback=feedback)
        reproj = rep.get("OUTPUT")
        if isinstance(reproj, str):
            reproj = QgsVectorLayer(reproj, "boundary_utm", "ogr")
        if reproj is None or not reproj.isValid():
            raise Exception(tr("Failed to reproject boundary to UTM."))
        contorno_layer = reproj

    # 1) snapped reference grid
    gt, (rows, cols) = compute_grid(contorno_layer.extent(), resolucao)
    ref_gt = gt
    ref_crs_wkt = contorno_layer.crs().toWkt()
    grid_shape = (rows, cols)
    target_crs_authid = contorno_layer.crs().authid()

    imagens_recortadas = []
    primeira_saida = None
    referencia_raster = None
    base_tmp = tempfile.mkdtemp(prefix="pz_warp_")

    tgt_crs = contorno_layer.crs()
    cont_ext = contorno_layer.extent()
    x_min, x_max = cont_ext.xMinimum(), cont_ext.xMaximum()
    y_min, y_max = cont_ext.yMinimum(), cont_ext.yMaximum()
    extent_str = f"{x_min},{x_max},{y_min},{y_max}"

    for raster in rasters:
        _say(tr("Processing"),
             tr("Reprojecting/resampling {}...").format(raster.name()))

        src_crs = raster.crs()

        # optional intersection check
        try:
            trf = QgsCoordinateTransform(src_crs, tgt_crs, QgsProject.instance().transformContext())
            src_ext_tgt = trf.transformBoundingBox(raster.extent())
            intersects = (
                (src_ext_tgt.xMaximum() > x_min) and (src_ext_tgt.xMinimum() < x_max) and
                (src_ext_tgt.yMaximum() > y_min) and (src_ext_tgt.yMinimum() < y_max)
            )
            if not intersects:
                _say(tr("Warning"),
                     tr("{}: raster does not intersect boundary after reprojection — skipping.").format(raster.name()),
                     level=1)
                continue
        except Exception:
            pass

        width_px = max(1, int(np.ceil((x_max - x_min) / resolucao)))
        height_px = max(1, int(np.ceil((y_max - y_min) / resolucao)))

        warp_tmp = os.path.join(base_tmp, f"_pz_warp_{uuid.uuid4().hex[:8]}.tif")
        out_clip = os.path.join(base_tmp, f"{raster.name()}_clip.tif")

        produced = False
        try:
            res_warp = processing.run("gdal:warpreproject", {
                'INPUT': raster.source(),
                'SOURCE_CRS': src_crs.authid(),
                'TARGET_CRS': tgt_crs.authid(),
                'RESAMPLING': 1,                               # bilinear
                'NODATA': None,
                'TARGET_RESOLUTION': [resolucao, resolucao],
                'TARGET_EXTENT': extent_str,
                'TARGET_EXTENT_CRS': tgt_crs.authid(),
                'MULTITHREADING': True,
                'DATA_TYPE': 0,
                'EXTRA': f'-tap -ts {width_px} {height_px}',
                'OUTPUT': warp_tmp
            }, context=context, feedback=feedback)
            cand = res_warp.get('OUTPUT', warp_tmp)
            produced = bool(cand) and os.path.exists(cand)
            if produced and os.path.normpath(cand) != os.path.normpath(warp_tmp):
                try:
                    import shutil
                    shutil.copyfile(cand, warp_tmp)
                except Exception:
                    pass
        except Exception:
            produced = False

        if not produced:
            try:
                gdal.Warp(
                    destNameOrDestDS=warp_tmp,
                    srcDSOrSrcDSTab=raster.source(),
                    format="GTiff",
                    dstSRS=tgt_crs.authid(),
                    xRes=resolucao, yRes=resolucao,
                    outputBounds=(x_min, y_min, x_max, y_max),
                    resampleAlg=gdal.GRA_Bilinear,
                    warpOptions=["MULTITHREAD=YES", "TARGET_ALIGNED_PIXELS=TRUE"],
                    creationOptions=["COMPRESS=LZW", "TILED=YES"],
                )
                produced = os.path.exists(warp_tmp)
            except Exception:
                produced = False

        if not produced:
            raise Exception(tr("Warp produced no output."))

        _say(tr("Processing"),
             tr("Clipping {} by boundary...").format(raster.name()))

        processing.run("gdal:cliprasterbymasklayer", {
            'INPUT': warp_tmp,
            'MASK': contorno_layer,
            'SOURCE_CRS': tgt_crs.authid(),
            'TARGET_CRS': tgt_crs.authid(),
            'RESAMPLING': 0,
            'NODATA': None,
            'ALPHA_BAND': False,
            'CROP_TO_CUTLINE': True,
            'KEEP_RESOLUTION': True,
            'TARGET_RESOLUTION': None,
            'OUTPUT': out_clip
        }, context=context, feedback=feedback)

        layer_saida = QgsRasterLayer(out_clip, f"{raster.name()}_clip")
        if not layer_saida.isValid():
            raise Exception(tr("Invalid output layer."))
        imagens_recortadas.append(layer_saida)

        if primeira_saida is None:
            primeira_saida = layer_saida
            referencia_raster = layer_saida

    if primeira_saida is None:
        raise Exception(tr("Resampling failed."))

    # 2) centroid points + sampling
    _say(tr("Processing"),
         tr("Generating centroid points..."))

    pontos_result = processing.run("native:pixelstopoints", {
        'INPUT_RASTER': primeira_saida.source(),
        'RASTER_BAND': 1,
        'FIELD_NAME': 'valor',
        'OUTPUT': 'TEMPORARY_OUTPUT'
    }, context=context, feedback=feedback)

    output_pontos = pontos_result['OUTPUT']
    layer_pontos = QgsVectorLayer(output_pontos, "Pontos_centroides", "ogr") \
        if isinstance(output_pontos, str) else output_pontos
    if not layer_pontos.isValid():
        raise Exception(tr("Invalid points layer."))

    for raster in imagens_recortadas:
        nome_campo = raster.name()
        _say(tr("Processing"),
             tr("Extracting values from {}...").format(nome_campo))

        result = processing.run("qgis:rastersampling", {
            'INPUT': layer_pontos,
            'RASTERCOPY': raster,
            'COLUMN_PREFIX': nome_campo + '_',
            'OUTPUT': 'TEMPORARY_OUTPUT'
        }, context=context, feedback=feedback)

        output_amostras = result['OUTPUT']
        layer_pontos = QgsVectorLayer(output_amostras, "Amostras_atribuidas", "ogr") \
            if isinstance(output_amostras, str) else output_amostras
        if not layer_pontos.isValid():
            raise Exception(tr("Failed to load layer with values from {}.").format(nome_campo))

    features = []
    campos = [f.name() for f in layer_pontos.fields()]
    for feat in layer_pontos.getFeatures():
        attrs = feat.attributes()
        if None not in attrs:
            geom = feat.geometry()
            if geom and not geom.isMultipart():
                ponto = geom.asPoint()
                linha = {'X': ponto.x(), 'Y': ponto.y()}
                linha.update({campos[i]: attr for i, attr in enumerate(attrs)})
                features.append(linha)

    df = pd.DataFrame(features)
    df, n_removed, zero_var_cols = limpar_dataframe(df, pd)

    matriz = None
    colunas = []
    if df is not None and not df.empty:
        dfnum = df.select_dtypes(include=[np.number]).copy()
        for col_drop in ['X', 'Y', 'valor']:
            if col_drop in dfnum.columns:
                dfnum = dfnum.drop(columns=[col_drop])
        matriz = dfnum.values
        colunas = dfnum.columns.tolist()

    # confirm metadata from the reference raster
    try:
        ref_path = primeira_saida.dataProvider().dataSourceUri().split("|")[0]
        ds_chk = gdal.Open(ref_path)
        if ds_chk:
            ref_gt = ds_chk.GetGeoTransform()
            ref_crs_wkt = ds_chk.GetProjection()
            grid_shape = (ds_chk.RasterYSize, ds_chk.RasterXSize)
    except Exception:
        pass

    return ResampleResult(
        df=df, ref_gt=ref_gt, ref_crs_wkt=ref_crs_wkt, grid_shape=grid_shape,
        referencia_raster=referencia_raster,
        matriz_variaveis_originais=matriz, colunas_variaveis_originais=colunas,
        n_removed=n_removed, zero_var_cols=zero_var_cols,
        target_crs_authid=target_crs_authid, reprojected=reprojected,
    )
