# -*- coding: utf-8 -*-
"""KMeans clustering, elbow + silhouette (pure backend, no UI)."""
from dataclasses import dataclass
from typing import Any

import numpy as np

from .deps import DependencyMissing


def standardize(matrix):
    """z-score standardize a 2D array (used for the 'original variables' path)."""
    try:
        from sklearn.preprocessing import StandardScaler
    except Exception:
        raise DependencyMissing("scikit-learn")
    return StandardScaler().fit_transform(matrix)


@dataclass
class ElbowResult:
    ks: list
    inertia: list
    silhouettes: list


def elbow_silhouette(dados, k_min: int, k_max: int) -> ElbowResult:
    """Run KMeans for k in [k_min, k_max], collecting inertia + silhouette."""
    try:
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score
    except Exception:
        raise DependencyMissing("scikit-learn")

    ks = list(range(k_min, k_max + 1))
    inercia = []
    silhuetas = []
    for k in ks:
        kmeans = KMeans(n_clusters=k, random_state=0, n_init=10)
        kmeans.fit(dados)
        inercia.append(kmeans.inertia_)
        try:
            labels = kmeans.labels_
            s = silhouette_score(dados, labels) if len(np.unique(labels)) > 1 else float("nan")
        except Exception:
            s = float("nan")
        silhuetas.append(s)

    return ElbowResult(ks=ks, inertia=inercia, silhouettes=silhuetas)


def final_kmeans(dados, n_zonas: int):
    """Fit KMeans and return 0-based labels."""
    try:
        from sklearn.cluster import KMeans
    except Exception:
        raise DependencyMissing("scikit-learn")
    modelo = KMeans(n_clusters=n_zonas, random_state=0, n_init=10)
    return modelo.fit_predict(dados)


def silhouette_kmeans(X, labels, max_samples=10000, random_state=0):
    """Silhouette score with subsampling for large inputs. nan if unavailable."""
    try:
        from sklearn.metrics import silhouette_score
    except Exception:
        return float("nan")
    n = X.shape[0]
    if n > max_samples:
        rng = np.random.default_rng(random_state)
        idx = rng.choice(n, size=max_samples, replace=False)
        return float(silhouette_score(X[idx], labels[idx], metric="euclidean"))
    return float(silhouette_score(X, labels, metric="euclidean"))
