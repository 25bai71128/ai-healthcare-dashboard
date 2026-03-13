"""Model evaluation utilities (classification metrics).

Designed for offline evaluation scripts and CI checks. Not used by the runtime
server unless explicitly imported.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score


def _as_1d(array: Any) -> np.ndarray:
    values = np.asarray(array)
    if values.ndim != 1:
        values = values.reshape(-1)
    return values


def classification_metrics(
    y_true: Any,
    *,
    y_pred: Any | None = None,
    y_score: Any | None = None,
    threshold: float = 0.5,
) -> dict[str, Any]:
    """Compute core classification metrics.

    - If `y_score` is provided, `y_pred` is derived via `y_score >= threshold`.
    - ROC-AUC is computed when `y_score` is available and labels are suitable.
    """

    y_true_arr = _as_1d(y_true)
    if y_score is not None:
        y_score_arr = _as_1d(y_score).astype(float)
        y_pred_arr = (y_score_arr >= float(threshold)).astype(int)
    elif y_pred is not None:
        y_score_arr = None
        y_pred_arr = _as_1d(y_pred)
    else:
        raise ValueError("Provide either y_pred or y_score")

    labels = np.unique(y_true_arr)
    average = "binary" if labels.size <= 2 else "macro"

    metrics: dict[str, Any] = {
        "accuracy": float(accuracy_score(y_true_arr, y_pred_arr)),
        "precision": float(precision_score(y_true_arr, y_pred_arr, average=average, zero_division=0)),
        "recall": float(recall_score(y_true_arr, y_pred_arr, average=average, zero_division=0)),
        "f1": float(f1_score(y_true_arr, y_pred_arr, average=average, zero_division=0)),
        "confusion_matrix": confusion_matrix(y_true_arr, y_pred_arr).tolist(),
        "support": int(y_true_arr.size),
        "average": average,
        "threshold": float(threshold),
    }

    if y_score_arr is not None:
        try:
            if labels.size <= 2:
                metrics["roc_auc"] = float(roc_auc_score(y_true_arr, y_score_arr))
            else:
                metrics["roc_auc"] = float(roc_auc_score(y_true_arr, y_score_arr, multi_class="ovr", average="macro"))
        except Exception:
            metrics["roc_auc"] = None
    else:
        metrics["roc_auc"] = None

    return metrics


def _extract_scores(model: Any, x: pd.DataFrame) -> tuple[np.ndarray | None, np.ndarray]:
    """Return (y_score, y_pred) from a sklearn-like model."""

    if hasattr(model, "predict_proba"):
        proba = np.asarray(model.predict_proba(x), dtype=float)
        if proba.ndim == 2 and proba.shape[1] >= 2:
            y_score = proba[:, 1]
        else:
            y_score = np.max(proba, axis=1)
        y_pred = np.asarray(model.predict(x))
        return _as_1d(y_score), _as_1d(y_pred)

    if hasattr(model, "decision_function"):
        scores = _as_1d(model.decision_function(x)).astype(float)
        # Map to (0,1) for AUC comparability.
        y_score = 1.0 / (1.0 + np.exp(-scores))
        y_pred = _as_1d(model.predict(x))
        return _as_1d(y_score), _as_1d(y_pred)

    y_pred = _as_1d(model.predict(x))
    return None, y_pred


def evaluate_csv(
    model_path: str | Path,
    dataset_path: str | Path,
    *,
    target: str,
    features: list[str] | None = None,
    threshold: float = 0.5,
) -> dict[str, Any]:
    model_path = Path(model_path)
    dataset_path = Path(dataset_path)

    model = joblib.load(model_path)
    data = pd.read_csv(dataset_path)
    if target not in data.columns:
        raise ValueError(f"Missing target column '{target}' in dataset")

    x = data[features] if features else data.drop(columns=[target])
    y_true = data[target]

    y_score, y_pred = _extract_scores(model, x)
    metrics = classification_metrics(y_true, y_pred=y_pred, y_score=y_score, threshold=threshold)

    return {
        "model_path": str(model_path),
        "dataset_path": str(dataset_path),
        "target": target,
        "features_used": list(x.columns),
        "metrics": metrics,
    }


def _main() -> None:  # pragma: no cover
    parser = argparse.ArgumentParser(description="Evaluate a saved model against a CSV dataset.")
    parser.add_argument("--model", required=True, help="Path to joblib/pkl model file")
    parser.add_argument("--data", required=True, help="Path to CSV dataset")
    parser.add_argument("--target", required=True, help="Target column name")
    parser.add_argument("--features", nargs="*", default=None, help="Optional explicit feature columns")
    parser.add_argument("--threshold", type=float, default=0.5, help="Threshold for converting scores to predictions")
    args = parser.parse_args()

    payload = evaluate_csv(
        args.model,
        args.data,
        target=args.target,
        features=list(args.features) if args.features else None,
        threshold=float(args.threshold),
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":  # pragma: no cover
    _main()

