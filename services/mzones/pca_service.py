# -*- coding: utf-8 -*-
"""PCA service (pure backend, no UI)."""
from dataclasses import dataclass
from typing import Any

from .deps import DependencyMissing, import_pandas
from .i18n import tr


@dataclass
class PCAResult:
    scores: Any                 # ndarray (n_samples, n_components)
    eigenvalues: Any            # ndarray
    variance_pct: Any           # ndarray
    cumulative_pct: Any         # ndarray
    columns: list               # variable names used
    relatorio_pca: Any          # DataFrame (loadings, "Variável" + PC columns)
    variancia_explicada: Any    # DataFrame (Componente/Autovalor/Variância/Acumulada)


def run_pca(df) -> PCAResult:
    """Standardize numeric variables and fit a full PCA.

    Raises DependencyMissing / ValueError(message) on problems.
    """
    pd = import_pandas()
    try:
        from sklearn.preprocessing import StandardScaler
        from sklearn.decomposition import PCA
    except Exception:
        raise DependencyMissing("scikit-learn")

    if df is None or df.empty:
        raise ValueError(tr("No data loaded. Run the resampling step first."))

    df = df.copy()
    colunas_usar = [c for c in df.columns if c not in ['X', 'Y', 'valor']]
    if not colunas_usar:
        raise ValueError(tr("No numeric variables for PCA."))

    dados = df[colunas_usar]
    if dados.shape[0] < 2:
        raise ValueError(tr("Insufficient data for PCA (less than 2 rows)."))

    dados_padronizados = StandardScaler().fit_transform(dados)
    pca = PCA()
    componentes = pca.fit_transform(dados_padronizados)

    variancias = pca.explained_variance_ratio_ * 100.0
    acumulada = variancias.cumsum()
    autovalores = pca.explained_variance_

    relatorio_pca = pd.DataFrame(
        pca.components_.T,
        columns=[f"PC{i+1}" for i in range(len(variancias))],
        index=colunas_usar
    ).reset_index().rename(columns={"index": "Variável"})

    variancia_explicada = pd.DataFrame({
        "Componente": [f"PC{i+1}" for i in range(len(variancias))],
        "Autovalor (λ)": autovalores,
        "Variância (%)": variancias,
        "Acumulada (%)": acumulada
    })

    return PCAResult(
        scores=componentes,
        eigenvalues=autovalores,
        variance_pct=variancias,
        cumulative_pct=acumulada,
        columns=colunas_usar,
        relatorio_pca=relatorio_pca,
        variancia_explicada=variancia_explicada,
    )
