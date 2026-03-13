"""SHAP wrapper with defensive fallbacks.

This module is optional at runtime; `shap` is only used if installed.
"""

from __future__ import annotations

from typing import Any

import numpy as np

try:  # Optional dependency.
    import shap  # type: ignore
except Exception:  # pragma: no cover
    shap = None


def try_shap_contributions(model: Any, input_features: np.ndarray, feature_names: list[str]) -> dict[str, Any] | None:
    """Return SHAP contributions for a single instance or None."""

    if shap is None:
        return None

    array = np.array(input_features, dtype=float)
    if array.ndim == 1:
        array = array.reshape(1, -1)
    if array.shape[0] != 1:
        array = array[:1]

    try:
        explainer = shap.Explainer(model)
        values = explainer(array)
        raw_values = np.array(values.values[0], dtype=float).reshape(-1)
        if raw_values.size != len(feature_names):
            return None
        return {
            "method": "shap",
            "values": {feature_names[idx]: float(raw_values[idx]) for idx in range(len(feature_names))},
        }
    except Exception:
        return None

