# -*- coding: utf-8 -*-
"""PZSession: explicit shared-state object.

Replaces the scattered `self.*` attributes on PrecisionZonesPlugin and the
dialog's `_fetch_parent_attr` reach-back hack. The plugin owns one instance;
the dialog holds a reference (for PC-raster export); controllers read/write it.
"""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class PZSession:
    # Sampled / loaded data
    dados_amostrados: Any = None                    # pandas DataFrame
    matriz_variaveis_originais: Any = None          # numpy ndarray
    colunas_variaveis_originais: Optional[list] = None

    # PCA outputs
    pca_transformada: Any = None                    # numpy ndarray (scores)
    pca_scores: Any = None                          # alias kept for clarity
    relatorio_pca: Any = None                       # DataFrame (loadings)
    variancia_explicada: Any = None                 # DataFrame

    # Clustering / elbow
    tabela_elbow: Any = None                        # DataFrame
    _ultima_fonte_tag: Optional[str] = None         # "PCA" | "Orig"
    _ultima_pcs: Optional[int] = None
    _ultimo_kminmax: Optional[tuple] = None

    # Reference grid metadata
    ref_gt: Optional[tuple] = None                  # geotransform (6 floats)
    ref_crs_wkt: Optional[str] = None
    ref_crs_authid: Optional[str] = None            # working CRS authid (auto-UTM if reprojected)
    grid_shape: Optional[tuple] = None              # (rows, cols)
    res_alvo: Optional[float] = None                # resolution (m)
    referencia_raster: Any = None                   # QgsRasterLayer

    # Export
    pasta_exportacao: Optional[str] = None

    # Layer lookups populated when the dialog opens
    vector_layers: dict = field(default_factory=dict)
    raster_layers: dict = field(default_factory=dict)

    def has_ref_metadata(self) -> bool:
        return (self.ref_gt is not None and self.ref_crs_wkt is not None
                and self.grid_shape is not None)

    def resolve_pca_scores(self):
        """Return (scores, n_components) or (None, 0)."""
        scores = self.pca_scores if self.pca_scores is not None else self.pca_transformada
        if scores is None:
            return None, 0
        ncomp = scores.shape[1] if hasattr(scores, "shape") and len(scores.shape) == 2 else 0
        return scores, ncomp
