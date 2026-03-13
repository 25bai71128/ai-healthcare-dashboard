"""LIME wrapper with defensive fallbacks.

This module is optional at runtime; `lime` is only used if installed.
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np

try:  # Optional dependency.
    from lime.lime_tabular import LimeTabularExplainer  # type: ignore
except Exception:  # pragma: no cover
    LimeTabularExplainer = None


def _default_training_data(instance: np.ndarray, *, rng: np.random.Generator, samples: int = 256) -> np.ndarray:
    # Use a small jittered cloud around the instance so LIME can discretize continuous features.
    base = np.repeat(instance.reshape(1, -1), int(max(32, samples)), axis=0)
    scale = np.maximum(np.abs(instance).reshape(1, -1) * 0.05, 0.02)
    jitter = rng.normal(loc=0.0, scale=scale, size=base.shape)
    return base + jitter


def _make_predict_proba(model: Any) -> Callable[[np.ndarray], np.ndarray]:
    if hasattr(model, "predict_proba"):
        return lambda x: np.asarray(model.predict_proba(x), dtype=float)

    def fallback(x: np.ndarray) -> np.ndarray:
        preds = np.asarray(model.predict(x), dtype=float).reshape(-1)
        preds = np.clip(preds, 0.0, 1.0)
        # Approximate binary probabilities.
        return np.stack([1.0 - preds, preds], axis=1)

    return fallback


def try_lime_contributions(
    model: Any,
    input_features: np.ndarray,
    feature_names: list[str],
    *,
    training_data: np.ndarray | None = None,
    random_state: int = 42,
) -> dict[str, Any] | None:
    """Return LIME contributions for a single instance or None."""

    if LimeTabularExplainer is None:
        return None

    array = np.array(input_features, dtype=float)
    if array.ndim == 1:
        array = array.reshape(1, -1)
    if array.shape[0] != 1:
        array = array[:1]

    if array.shape[1] != len(feature_names):
        return None

    rng = np.random.default_rng(int(random_state))
    train = np.array(training_data, dtype=float) if training_data is not None else _default_training_data(array[0], rng=rng)
    if train.ndim != 2 or train.shape[1] != array.shape[1]:
        train = _default_training_data(array[0], rng=rng)

    predict_proba = _make_predict_proba(model)

    try:
        # Discover class count cheaply for nicer output.
        proba = predict_proba(array)
        class_count = int(proba.shape[1]) if proba.ndim == 2 else 2
        class_names = [f"class_{idx}" for idx in range(class_count)]
        class_id = int(np.argmax(proba[0])) if proba.ndim == 2 and proba.shape[0] else 0

        explainer = LimeTabularExplainer(
            train,
            feature_names=feature_names,
            class_names=class_names,
            mode="classification",
            discretize_continuous=True,
            random_state=int(random_state),
        )
        explanation = explainer.explain_instance(array[0], predict_proba, num_features=len(feature_names), num_samples=220)
        local = explanation.local_exp.get(class_id, [])
        values = {feature_names[int(idx)]: float(weight) for idx, weight in local if int(idx) < len(feature_names)}
        if not values:
            return None
        return {"method": "lime", "values": values}
    except Exception:
        return None

