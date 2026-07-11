# -*- coding: utf-8 -*-
"""Zones raster generation: rasterize per-point cluster ids onto the reference
grid. Pure backend (no QMessageBox)."""
import os
import tempfile

from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsField,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
)
from qgis.PyQt.QtCore import QVariant
from qgis import processing

from .i18n import tr


def rasterize_zones(df_xyz, crs_authid: str, ref_gt: tuple, grid_shape: tuple,
                    out_path: str):
    """Write a point GeoPackage from df (columns X, Y, Zona) and rasterize the
    'Zona' field onto the reference grid. Returns out_path."""
    mem_layer = QgsVectorLayer(f"Point?crs={crs_authid}", "zonas_pts_mem", "memory")
    prov = mem_layer.dataProvider()
    prov.addAttributes([QgsField("Zona", QVariant.Int)])
    mem_layer.updateFields()

    feats = []
    for X, Y, Z in df_xyz[["X", "Y", "Zona"]].itertuples(index=False):
        f = QgsFeature(mem_layer.fields())
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(float(X), float(Y))))
        f.setAttribute("Zona", int(Z))
        feats.append(f)
    prov.addFeatures(feats)
    mem_layer.updateExtents()

    tmp_gpkg = os.path.join(tempfile.gettempdir(), "pz_zonas_pts.gpkg")
    if os.path.exists(tmp_gpkg):
        try:
            os.remove(tmp_gpkg)
        except Exception:
            pass

    save_opts = QgsVectorFileWriter.SaveVectorOptions()
    save_opts.driverName = "GPKG"
    save_opts.layerName = "zonas_pts"
    save_opts.fileEncoding = "UTF-8"

    ret = QgsVectorFileWriter.writeAsVectorFormatV3(
        mem_layer, tmp_gpkg, QgsProject.instance().transformContext(), save_opts
    )

    err = None
    err_msg = ""
    try:
        err = ret[0]
        err_msg = ret[1] if len(ret) > 1 else ""
    except Exception:
        try:
            err = ret.error
            err_msg = ret.errorMessage
        except Exception:
            err = QgsVectorFileWriter.NoError

    if err != QgsVectorFileWriter.NoError:
        raise Exception(tr("Failed to save temporary GeoPackage: {}").format(err_msg))

    pontos_src = QgsVectorLayer(tmp_gpkg + "|layername=zonas_pts", "zonas_pts", "ogr")
    if not pontos_src.isValid():
        raise Exception(tr("Temporary (GeoPackage) layer is invalid."))

    if ref_gt is None or grid_shape is None:
        raise Exception(tr("Reference grid not available. Run the resampling step."))

    x0, px, _, y0, _, neg_py = ref_gt
    cols = int(grid_shape[1])
    rows = int(grid_shape[0])
    extent_str = f"{x0},{x0 + cols * px},{y0 - rows * abs(neg_py)},{y0}"

    processing.run("gdal:rasterize", {
        'INPUT': pontos_src,
        'FIELD': 'Zona',
        'BURN': 0,
        'USE_Z': False,
        'UNITS': 0,
        'WIDTH': cols,
        'HEIGHT': rows,
        'EXTENT': extent_str,
        'NODATA': 0,
        'INIT': 0,
        'INVERT': False,
        'DATA_TYPE': 2,
        'EXTRA': '',
        'OUTPUT': out_path
    })
    return out_path
