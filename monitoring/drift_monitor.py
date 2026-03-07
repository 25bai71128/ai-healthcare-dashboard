"""Drift and prediction quality monitoring utilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASELINE_DATA = PROJECT_ROOT / "data" / "health_data.csv"
FEATURES = ["age", "blood_pressure", "cholesterol"]
_BASELINE_CACHE: BaselineStats | None = None
_BASELINE_SIGNATURE: int | None = None


@dataclass
class BaselineStats:
    """Baseline means and std-dev values for drift checks."""

    means: dict[str, float]
    stds: dict[str, float]


def _load_baseline_stats() -> BaselineStats:
    """Load baseline stats from training dataset for drift scoring."""
    if not BASELINE_DATA.exists():
        return BaselineStats(
            means={feature: 0.0 for feature in FEATURES},
            stds={feature: 1.0 for feature in FEATURES},
        )

    frame = pd.read_csv(BASELINE_DATA)
    means: dict[str, float] = {}
    stds: dict[str, float] = {}

    for feature in FEATURES:
        if feature in frame.columns:
            means[feature] = float(frame[feature].mean())
            std = float(frame[feature].std())
            stds[feature] = std if std > 0 else 1.0
        else:
            means[feature] = 0.0
            stds[feature] = 1.0

    return BaselineStats(means=means, stds=stds)


def _baseline_signature() -> int:
    if not BASELINE_DATA.exists():
        return -1
    return int(BASELINE_DATA.stat().st_mtime_ns)


def _get_baseline_stats() -> BaselineStats:
    """Cache baseline stats and refresh only when dataset changes."""
    global _BASELINE_CACHE, _BASELINE_SIGNATURE

    signature = _baseline_signature()
    if _BASELINE_CACHE is None or signature != _BASELINE_SIGNATURE:
        _BASELINE_CACHE = _load_baseline_stats()
        _BASELINE_SIGNATURE = signature
    return _BASELINE_CACHE


def assess_prediction(
    patient_data: dict[str, Any],
    model_predictions: dict[str, dict[str, Any]],
    health_score: dict[str, Any],
) -> dict[str, Any]:
    """Compute drift, confidence, and consistency diagnostics."""
    baseline_stats = _get_baseline_stats()
    z_scores: dict[str, float] = {}
    drift_flags: dict[str, bool] = {}

    for feature in FEATURES:
        value = float(patient_data.get(feature, 0.0))
        mean_value = baseline_stats.means.get(feature, 0.0)
        std_value = baseline_stats.stds.get(feature, 1.0)

        z_score = round((value - mean_value) / std_value, 3)
        z_scores[feature] = z_score
        drift_flags[feature] = abs(z_score) >= 3.0

    probabilities = [float(item.get("probability", 0.0)) for item in model_predictions.values()]
    avg_probability = mean(probabilities) if probabilities else 0.0
    high_disagreement = (max(probabilities) - min(probabilities)) > 0.40 if len(probabilities) > 1 else False

    return {
        "z_scores": z_scores,
        "drift_flags": drift_flags,
        "drift_detected": any(drift_flags.values()),
        "avg_model_probability": round(avg_probability, 4),
        "high_model_disagreement": high_disagreement,
        "global_risk": health_score.get("overall_health_score", 0.0),
    }
