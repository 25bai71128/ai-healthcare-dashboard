"""Unsupervised patient pattern learning: clustering + anomaly detection.

This module is intentionally model-light: it operates on tabular numeric features and
returns JSON-serialisable payloads that can be plotted directly in the dashboard.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN, KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler


def _coerce_numeric_frame(patients: list[dict[str, Any]], features: list[str] | None) -> tuple[pd.DataFrame, list[str]]:
    if not patients:
        raise ValueError("patients must be a non-empty list")

    frame = pd.DataFrame(patients)
    if features:
        missing = [name for name in features if name not in frame.columns]
        if missing:
            raise ValueError(f"Missing feature(s): {', '.join(missing)}")
        numeric = frame[features].copy()
        used = list(features)
    else:
        numeric = frame.select_dtypes(include=["number"]).copy()
        used = [str(col) for col in numeric.columns]
        if not used:
            # Coerce everything and keep numeric-looking columns (common for JSON inputs).
            numeric = frame.apply(pd.to_numeric, errors="coerce")
            used = [str(col) for col in numeric.columns if numeric[col].notna().any()]
            numeric = numeric[used]

    if not used:
        raise ValueError("No numeric features found for clustering")

    numeric = numeric.apply(pd.to_numeric, errors="coerce")
    # Fill missing values with median; if a column is all NaNs, use 0.
    medians = numeric.median(numeric_only=True)
    numeric = numeric.fillna(medians).fillna(0.0)

    # Keep as float64 for sklearn stability.
    return numeric.astype(float), used


def cluster_patients(
    patients: list[dict[str, Any]],
    *,
    features: list[str] | None = None,
    n_clusters: int = 3,
    pca_components: int = 2,
    dbscan_eps: float = 0.85,
    dbscan_min_samples: int = 5,
    random_state: int = 42,
) -> dict[str, Any]:
    """Cluster patients and flag anomalies using KMeans + DBSCAN.

    Parameters
    - patients: list of dicts containing numeric fields.
    - features: optional explicit list of numeric feature names to use.
    - n_clusters: KMeans cluster count. Auto-clipped to [1, n_samples].
    - pca_components: number of PCA components for projection; when set to 2 it
      returns `projection` points suitable for scatter plots.
    - dbscan_*: DBSCAN parameters used on the PCA space (or scaled space if PCA
      is disabled).
    """

    numeric, used_features = _coerce_numeric_frame(patients, features)
    values = numeric.to_numpy(dtype=float)
    n_samples, n_features = values.shape

    # Standardize so scale differences (e.g., glucose vs temperature) don't dominate.
    scaler = StandardScaler()
    scaled = scaler.fit_transform(values)

    # PCA projection for visualisation (and as a compact space for DBSCAN).
    pca_result: np.ndarray
    explained_variance: list[float] = []
    if pca_components and n_features > 1:
        components = int(max(1, min(pca_components, n_features, n_samples)))
        pca = PCA(n_components=components, random_state=random_state)
        pca_result = pca.fit_transform(scaled)
        explained_variance = [float(x) for x in getattr(pca, "explained_variance_ratio_", [])]
    else:
        pca_result = scaled

    # KMeans clustering (stable defaults for small datasets).
    effective_clusters = int(max(1, min(int(n_clusters), n_samples)))
    kmeans = KMeans(n_clusters=effective_clusters, n_init="auto", random_state=random_state)
    cluster_labels = kmeans.fit_predict(pca_result)

    # DBSCAN anomaly detection: label -1 is "noise" (outlier) points.
    dbscan = DBSCAN(eps=float(dbscan_eps), min_samples=int(max(1, dbscan_min_samples)))
    anomaly_labels = dbscan.fit_predict(pca_result)
    is_anomaly = anomaly_labels == -1

    projection: list[dict[str, Any]] = []
    if pca_result.shape[1] >= 2:
        projection = [
            {"x": float(point[0]), "y": float(point[1]), "cluster": int(cluster_labels[idx]), "anomaly": bool(is_anomaly[idx])}
            for idx, point in enumerate(pca_result)
        ]
    else:
        projection = [
            {"x": float(pca_result[idx][0]), "y": 0.0, "cluster": int(cluster_labels[idx]), "anomaly": bool(is_anomaly[idx])}
            for idx in range(n_samples)
        ]

    # Summaries useful for UI.
    counts = Counter(int(label) for label in cluster_labels)
    anomaly_count = int(np.sum(is_anomaly))

    cluster_profiles: dict[str, dict[str, float]] = {}
    for label in sorted(counts):
        mask = cluster_labels == label
        if not np.any(mask):
            continue
        mean_vals = np.mean(values[mask], axis=0)
        cluster_profiles[str(label)] = {used_features[i]: round(float(mean_vals[i]), 4) for i in range(n_features)}

    anomaly_rows: list[dict[str, Any]] = []
    for idx in np.where(is_anomaly)[0].tolist():
        row = {used_features[i]: float(values[idx][i]) for i in range(n_features)}
        anomaly_rows.append({"index": int(idx), "features": row, "cluster": int(cluster_labels[idx])})

    return {
        "schema_version": 1,
        "features_used": used_features,
        "n_samples": int(n_samples),
        "n_clusters": int(effective_clusters),
        "pca_components": int(pca_result.shape[1]),
        "pca_explained_variance_ratio": explained_variance,
        "clusters": [int(x) for x in cluster_labels.tolist()],
        "projection": projection,
        "cluster_profiles": cluster_profiles,
        "anomalies": anomaly_rows,
        "summary": {
            "cluster_counts": {str(k): int(v) for k, v in counts.items()},
            "anomaly_count": int(anomaly_count),
        },
    }

