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


def elbow_silhouette(dados, k_min: int, k_max: int,
                     progress=None, should_stop=None) -> ElbowResult:
    """Run KMeans for k in [k_min, k_max], collecting inertia + silhouette.

    Silhouette is subsampled (see ``silhouette_kmeans``) to stay O(n) on large
    grids. ``progress(done, total)`` is called after each k; ``should_stop()``
    is checked before each k so a worker thread can bail out early."""
    try:
        from sklearn.cluster import KMeans
    except Exception:
        raise DependencyMissing("scikit-learn")

    ks = list(range(k_min, k_max + 1))
    inercia = []
    silhuetas = []
    for i, k in enumerate(ks):
        if should_stop is not None and should_stop():
            break
        kmeans = KMeans(n_clusters=k, random_state=0, n_init=10)
        kmeans.fit(dados)
        inercia.append(kmeans.inertia_)
        try:
            labels = kmeans.labels_
            s = (silhouette_kmeans(dados, labels)
                 if len(np.unique(labels)) > 1 else float("nan"))
        except Exception:
            s = float("nan")
        silhuetas.append(s)
        if progress is not None:
            progress(i + 1, len(ks))

    return ElbowResult(ks=ks[:len(inercia)], inertia=inercia, silhouettes=silhuetas)


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
